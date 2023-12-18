import os.path
import tarfile
import glob
import re
import json
import tempfile
import urllib3
import kubernetes.client
import kubernetes.config
import kubernetes.stream
from kubectl import exceptions


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def camel_to_snake(name: str) -> str:
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()


def snake_to_camel(name: str) -> str:
    name = name.split('_')
    return name[0] + ''.join(ele.title() for ele in name[1:])


def _prepare_body(body):
    """Ensure fields are in Camel Case"""
    if isinstance(body, dict):
        return {
            snake_to_camel(key): (
                _prepare_body(value) if key != 'data' else value)
            for key, value in body.items()}
    if isinstance(body, (list, tuple)):
        return [_prepare_body(sub) for sub in body]
    return body


def load_kubeconfig(host: str = None, api_key: str = None, certificate: str = None):
    if not host:
        kubernetes.config.load_kube_config()
        return
    configuration = kubernetes.client.Configuration()
    configuration.host = host
    if api_key:
        configuration.api_key['authorization'] = api_key
        configuration.api_key_prefix['authorization'] = 'Bearer'
    if certificate:
        # pylint: disable=consider-using-with
        cafile = tempfile.NamedTemporaryFile(delete=False)
        cafile.write(certificate)
        cafile.flush()
        configuration.ssl_ca_cert = cafile.name
    else:
        configuration.verify_ssl = False
    kubernetes.client.Configuration.set_default(configuration)


def _get_resource(obj: str) -> dict:
    api = kubernetes.client.CoreV1Api()
    for res in api.get_api_resources().to_dict()['resources']:
        if res['name'] == obj or res['kind'].lower() == obj.lower() or \
                (res['short_names'] and obj in res['short_names']):
            res['api'] = {
                'name': 'CoreV1Api',
                'version': 'v1',
                'group_version': 'v1'}
            return res
    global_api = kubernetes.client.ApisApi()
    api = kubernetes.client.CustomObjectsApi()
    for api_group in global_api.get_api_versions().to_dict()['groups']:
        for res in api.get_api_resources(
                api_group['name'],
                api_group['preferred_version']['version']).to_dict()['resources']:
            if res['name'] == obj or res['kind'].lower() == obj.lower() or \
                    (res['short_names'] and obj in res['short_names']):
                res['api'] = {
                    'name': 'CustomObjectsApi',
                    'group': api_group['name'],
                    'version': api_group['preferred_version']['version'],
                    'group_version': api_group['preferred_version']['group_version']}
                return res
    raise exceptions.KubectlTypeException(obj)


def _api_call(api_resource: str, verb: str, resource: str, **opts) -> dict:
    ftn = f"{verb}_{resource}"
    name = None
    if verb == 'list' and 'name' in opts:
        name = opts['name']
        del opts['name']
    api = getattr(kubernetes.client, api_resource)()
    try:
        objs = getattr(api, ftn)(**opts)
    except kubernetes.client.rest.ApiException as err:
        body = err.body
        try:
            body = json.loads(body)['message']
        except (ValueError, AttributeError):
            pass
        raise exceptions.KubectlBaseException(body) from err
    # pylint: disable=no-else-return
    if verb == 'list':
        if 'to_dict' in dir(objs):
            objs = objs.to_dict()['items']
        else:
            objs = objs['items']
        if name is None:
            return objs
        for obj in objs:
            if obj['metadata']['name'] == name:
                return obj
        return {}
    else:
        if 'to_dict' in dir(objs):
            return objs.to_dict()
        return objs


def scale(obj: str, name: str, namespace: str = None, replicas: int = 1) -> dict:
    namespace = namespace or 'default'
    resource = _get_resource(obj)
    if resource['kind'] not in ('Deployment', 'StatefulSet', 'ReplicaSet'):
        raise exceptions.KubectlResourceException
    if 'patch' not in resource['verbs']:
        raise exceptions.KubectlMethodException
    ftn = f"namespaced_{camel_to_snake(resource['kind'])}_scale"
    return _api_call(
        'AppsV1Api', 'patch', ftn,
        name=name, namespace=namespace,
        body={"spec": {'replicas': replicas}})


def get(obj: str, name: str = None, namespace: str = None,
        labels: str = None, all_namespaces: bool = False) -> dict:
    resource = _get_resource(obj)
    verb = 'get' if name else 'list'
    if verb not in resource['verbs']:
        raise exceptions.KubectlMethodException
    namespace = namespace or 'default'
    opts = {"label_selector": labels, "name": name}
    if resource['api']['name'] == 'CoreV1Api':
        ftn = camel_to_snake(resource['kind'])
        if resource['namespaced'] is True:
            if all_namespaces is True:
                ftn = f"{ftn}_for_all_namespaces"
            else:
                ftn = f"namespaced_{ftn}"
                opts['namespace'] = namespace
    else:
        opts['plural'] = resource['name']
        opts['group'] = resource['api']['group']
        opts['version'] = resource['api']['version']
        if all_namespaces is False and resource['namespaced'] is True:
            ftn = 'namespaced_custom_object'
            opts['namespace'] = namespace
        else:
            ftn = 'cluster_custom_object'
    return _api_call(resource['api']['name'], 'list', ftn, **opts)


def delete(obj: str, name: str, namespace: str = None) -> dict:
    namespace = namespace or 'default'
    resource = _get_resource(obj)
    if 'delete' not in resource['verbs']:
        raise exceptions.KubectlMethodException
    opts = {"name": name}
    if resource['api']['name'] == 'CoreV1Api':
        ftn = camel_to_snake(resource['kind'])
        if resource['namespaced'] is True:
            ftn = f"namespaced_{ftn}"
            opts['namespace'] = namespace
    else:
        opts['plural'] = resource['name']
        opts['group'] = resource['api']['group']
        opts['version'] = resource['api']['version']
        if resource['namespaced'] is True:
            ftn = 'namespaced_custom_object'
            opts['namespace'] = namespace
        else:
            ftn = 'cluster_custom_object'
    return _api_call(resource['api']['name'], 'delete', ftn, **opts)


def create(obj: str, name: str = None, namespace: str = None, body: dict = None) -> dict:
    body = body or {}
    namespace = namespace or 'default'
    if 'metadata' not in body:
        body['metadata'] = {}
    if name is not None and 'name' not in body['metadata']:
        body['metadata']['name'] = name
    if 'name' not in body['metadata']:
        raise exceptions.KubectlNameException
    resource = _get_resource(obj)
    if 'create' not in resource['verbs']:
        raise exceptions.KubectlMethodException
    if resource['namespaced'] is True and 'namespace' not in body['metadata']:
        body['metadata']['namespace'] = namespace
    if 'apiVersion' not in body:
        body['apiVersion'] = resource['api']['group_version']
    if 'kind' not in body:
        body['kind'] = resource['kind']
    opts = {"body": _prepare_body(body)}
    if resource['api']['name'] == 'CoreV1Api':
        ftn = camel_to_snake(resource['kind'])
        if resource['namespaced'] is True:
            ftn = f"namespaced_{ftn}"
            opts['namespace'] = body['metadata']['namespace']
    else:
        opts['plural'] = resource['name']
        opts['group'] = resource['api']['group']
        opts['version'] = resource['api']['version']
        if resource['namespaced'] is True:
            ftn = 'namespaced_custom_object'
            opts['namespace'] = body['metadata']['namespace']
        else:
            ftn = 'cluster_custom_object'
    return _api_call(resource['api']['name'], 'create', ftn, **opts)


def patch(obj: str, name: str = None, namespace: str = None, body: dict = None) -> dict:
    body = body or {}
    namespace = namespace or 'default'
    if 'metadata' not in body:
        body['metadata'] = {}
    if name is not None and 'name' not in body['metadata']:
        body['metadata']['name'] = name
    if 'name' not in body['metadata']:
        raise exceptions.KubectlNameException
    resource = _get_resource(obj)
    if 'patch' not in resource['verbs']:
        raise exceptions.KubectlMethodException
    if resource['namespaced'] is True and 'namespace' not in body['metadata']:
        body['metadata']['namespace'] = namespace
    if 'apiVersion' not in body:
        body['apiVersion'] = resource['api']['group_version']
    if 'kind' not in body:
        body['kind'] = resource['kind']
    opts = {"name": body['metadata']['name'], "body": _prepare_body(body)}
    if resource['api']['name'] == 'CoreV1Api':
        ftn = camel_to_snake(resource['kind'])
        if resource['namespaced'] is True:
            ftn = f"namespaced_{ftn}"
            opts['namespace'] = body['metadata']['namespace']
    else:
        opts['plural'] = resource['name']
        opts['group'] = resource['api']['group']
        opts['version'] = resource['api']['version']
        if resource['namespaced'] is True:
            ftn = 'namespaced_custom_object'
            opts['namespace'] = body['metadata']['namespace']
        else:
            ftn = 'cluster_custom_object'
    return _api_call(resource['api']['name'], 'patch', ftn, **opts)


def run(name: str, image: str, namespace: str = None, annotations: dict = None,
        labels: dict = None, env: dict = None, restart: str = 'Always') -> dict:
    annotations = annotations or {}
    env = env or {}
    namespace = namespace or 'default'
    labels = labels or {'run': name}
    body = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "labels": labels,
            "annotations": annotations,
            "name": name,
            "namespace": namespace},
        "spec": {
            "restartPolicy": restart,
            "containers": [{"image": image, "name": name}]}}
    envs = [{"name": k, "value": v} for k, v in env.items()]
    body['spec']['containers'][0]['env'] = envs
    return _api_call('CoreV1Api', 'create', 'namespaced_pod',
                     namespace=namespace, body=body)


def annotate(obj, name: str, namespace: str = None,
             overwrite: bool = False, **annotations) -> dict:
    body = get(obj, name, namespace)
    current = body['metadata'].get('annotations', {}) or {}
    if overwrite is False:
        for key in current:
            if key in annotations:
                raise exceptions.KubectlBaseException(
                    "error: overwrite is false but found the "
                    "following declared annotation(s): "
                    f"'{key}' already has a value ({current[key]})")
    current.update(annotations)
    body['metadata']['annotations'] = current
    return patch(obj, name, namespace, body)


def logs(name: str, namespace: str = None, container: str = None) -> str:
    namespace = namespace or 'default'
    api = kubernetes.client.CoreV1Api()
    resp = api.read_namespaced_pod(name=name, namespace=namespace).to_dict()
    if container is None:
        container = resp['spec']['containers'][0]['name']
    else:
        if container not in [ctn['name'] for ctn in resp['spec']['containers']]:
            raise exceptions.KubectlContainerNameException(name, namespace, container)
    return api.read_namespaced_pod_log(
        name,
        namespace,
        container=container)


def apply(body: dict) -> dict:
    name = body['metadata']['name']
    namespace = body['metadata'].get('namespace', None)
    obj = body['kind']
    if get(obj, name, namespace) == {}:
        return create(obj, name, namespace, body)
    return patch(obj, name, namespace, body)


def top(obj: str, namespace: str = None, all_namespaces: bool = False) -> dict:
    if obj not in ('pod', 'pods', 'node', 'nodes'):
        raise exceptions.KubectlBaseException(f'error: unknown command "{obj}"')
    obj = 'podmetrics' if obj in ('pod', 'pods') else 'nodemetrics'
    return get(obj, namespace=namespace, all_namespaces=all_namespaces)


# pylint: disable=redefined-builtin
def exec(name: str, command: list, namespace: str = None, container: str = None) -> str:
    namespace = namespace or 'default'
    api = kubernetes.client.CoreV1Api()
    resp = api.read_namespaced_pod(name=name, namespace=namespace).to_dict()
    if container is None:
        container = resp['spec']['containers'][0]['name']
    else:
        if container not in [ctn['name'] for ctn in resp['spec']['containers']]:
            raise exceptions.KubectlContainerNameException(name, namespace, container)
    resp = kubernetes.stream.stream(
        api.connect_get_namespaced_pod_exec,
        name,
        namespace,
        container=container,
        command=command,
        stderr=True, stdin=False,
        stdout=True, tty=False)
    return resp


def cp(name: str, local_path: str, remote_path: str,
       namespace: str = None, container: str = None, mode='PUSH') -> bool:
    if mode not in ('PULL', 'PUSH'):
        raise exceptions.KubectlBaseException(
            'value for "mode" can only be "PULL" (from the container) '
            'or "PUSH" (to the container)')
    namespace = namespace or 'default'
    api = kubernetes.client.CoreV1Api()
    resp = api.read_namespaced_pod(name=name, namespace=namespace).to_dict()
    if container is None:
        container = resp['spec']['containers'][0]['name']
    else:
        if container not in [ctn['name'] for ctn in resp['spec']['containers']]:
            raise exceptions.KubectlContainerNameException(name, namespace, container)
    if mode == 'PUSH':
        command = ['tar', 'xf', '-', '-C', remote_path]
        resp = kubernetes.stream.stream(
            api.connect_get_namespaced_pod_exec,
            name,
            namespace,
            container=container,
            command=command,
            stderr=True, stdin=True,
            stdout=True, tty=False,
            _preload_content=False)

        with tempfile.TemporaryFile() as tar_buffer:
            with tarfile.open(fileobj=tar_buffer, mode='w') as tar:
                for source_file in glob.glob(local_path):
                    tar.add(source_file)

            tar_buffer.seek(0)
            commands = []
            commands.append(tar_buffer.read())

            while resp.is_open():
                resp.update(timeout=1)
                if resp.peek_stdout():
                    print(f"STDOUT: {resp.read_stdout()}")
                if resp.peek_stderr():
                    print(f"STDERR: {resp.read_stderr()}")
                if commands:
                    c = commands.pop(0)
                    resp.write_stdin(c.decode())
                else:
                    break
            resp.close()
    else:
        command = ['tar', 'cf', '-', remote_path]
        resp = kubernetes.stream.stream(
            api.connect_get_namespaced_pod_exec,
            name,
            namespace,
            container=container,
            command=command,
            stderr=True, stdin=True,
            stdout=True, tty=False,
            _preload_content=False)
        with tempfile.TemporaryFile() as tar_buffer:
            while resp.is_open():
                resp.update(timeout=1)
                if resp.peek_stdout():
                    out = resp.read_stdout()
                    tar_buffer.write(out.encode())
                if resp.peek_stderr():
                    print(f"STDERR: {resp.read_stderr()}")
            resp.close()
            tar_buffer.flush()
            tar_buffer.seek(0)
            with tarfile.open(fileobj=tar_buffer, mode='r:') as tar:
                for member in tar.getmembers():
                    if os.path.isdir(local_path):
                        local_file = os.path.join(
                            local_path, os.path.basename(member.name))
                    else:
                        local_file = local_path
                    tar.makefile(member, local_file)
    return True


# def wait(obj: str, jsonpath: str, value: str, name: str = None,
#          namespace: str = None, labels: str = None, timeout: int = 60):
#     """
#     Examples:
#        kubectl.wait('pods', '{@[*].metadata.name}', 'nginx')
#     """
#     seconds = 0
#     if jsonpath[0] == '{' and jsonpath[-1] == '}':
#         jsonpath = jsonpath[1:-1]
#     if jsonpath[0] == '.':
#         jsonpath = jsonpath[1:]
#     query = jp.parse(jsonpath)
#     while True:
#         obj_value = get(obj, name, namespace, labels)
#         if any(match.value == value for match in query.find(obj_value)):
#             break
#         time.sleep(2)
#         seconds += 2
#         if seconds > timeout:
#             raise TimeoutError('timed out waiting for the condition')
#     return True
