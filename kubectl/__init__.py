"""
Kubectl helpers for python-kubernetes
That bunch of functions mimic kubectl behaviour and options
"""

import os.path
import atexit
import tarfile
import glob
import re
import json
import socket
import tempfile
import urllib3
import kubernetes.client
import kubernetes.config
import kubernetes.stream
from kubectl import exceptions


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
_temp_files = []
_resource_cache = []


def _cleanup_temp_files():
    # pylint: disable=global-statement
    global _temp_files
    for temp_file in _temp_files:
        try:
            os.remove(temp_file)
        except OSError:
            pass
    _temp_files = []


def camel_to_snake(name: str) -> str:
    """Converts Camel-style string to Snake-style string"""
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()


def snake_to_camel(name: str) -> str:
    """Converts Snake-style string to Camel-style string"""
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


def _find_container(name: str, namespace: str, container: str = None):
    api = kubernetes.client.CoreV1Api()
    resp = api.read_namespaced_pod(name=name, namespace=namespace).to_dict()
    if container is None:
        container = resp['spec']['containers'][0]['name']
    else:
        if container not in [ctn['name'] for ctn in resp['spec']['containers']]:
            raise exceptions.KubectlInvalidContainerException(name, namespace, container)
    return container


def connect(host: str = None, api_key: str = None, certificate: str = None):
    """Create configuration so python-kubernetes can access resources.
    With no arguments, Try to get config from ~/.kube/config or KUBECONFIG
    If set, certificate parameter is not Base64-encoded"""
    # pylint: disable=global-statement
    global _temp_files
    if not host:
        try:
            socket.gethostbyname_ex("kubernetes.default.svc.cluster.local")
            _in_cluster = True
        except socket.gaierror:
            _in_cluster = False
        try:
            if _in_cluster:
                kubernetes.config.load_incluster_config()
            else:
                kubernetes.config.load_kube_config()
        except kubernetes.config.config_exception.ConfigException as e:
            raise exceptions.KubectlConfigException(str(e))
        return
    configuration = kubernetes.client.Configuration()
    configuration.host = host
    if api_key:
        configuration.api_key['authorization'] = f'Bearer {api_key}'
    if certificate:
        # pylint: disable=consider-using-with
        cafile = tempfile.NamedTemporaryFile(delete=False)
        if isinstance(certificate, str):
            certificate = certificate.encode()
        cafile.write(certificate)
        cafile.flush()
        configuration.ssl_ca_cert = cafile.name
        if len(_temp_files) == 0:
            atexit.register(_cleanup_temp_files)
        _temp_files += [cafile.name]
    else:
        configuration.verify_ssl = False
    kubernetes.client.Configuration.set_default(configuration)


def _get_resource(obj: str) -> dict:
    """From a resource name or alias, extract the API name
    and version to use from api-resources"""
    # pylint: disable=global-statement
    global _resource_cache
    for _cache in _resource_cache:
        if _cache['name'] == obj or _cache['kind'].lower() == obj.lower() or \
                (_cache['short_names'] and obj in _cache['short_names']):
            return _cache
    api = kubernetes.client.CoreV1Api()
    for res in api.get_api_resources().to_dict()['resources']:
        if res['name'] == obj or res['kind'].lower() == obj.lower() or \
                (res['short_names'] and obj in res['short_names']):
            res['api'] = {
                'name': 'CoreV1Api',
                'version': 'v1',
                'group_version': 'v1'}
            _resource_cache += [res]
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
                _resource_cache += [res]
                return res
    raise exceptions.KubectlResourceTypeException(obj)


def _api_call(api_resource: str, verb: str, resource: str, **opts) -> dict:
    """Execute calls directly to python-kubernetes"""
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


def scale(obj: str, name: str, namespace: str = None,
          replicas: int = 1, dry_run: bool = False) -> dict:
    """Scale Apps resources
    :param obj: resource type
    :param name: resource name
    :param namespace: namespace
    :param replicas: number of expected replicas once scaled
    :returns: patch_namespaced_object_scale JSON
    :raises exceptions.KubectlResourceNotFoundException: if not a Apps resource"""
    namespace = namespace or 'default'
    resource = _get_resource(obj)
    if resource['kind'] not in ('Deployment', 'StatefulSet', 'ReplicaSet'):
        raise exceptions.KubectlResourceNotFoundException
    if 'patch' not in resource['verbs']:
        raise exceptions.KubectlMethodException
    ftn = f"namespaced_{camel_to_snake(resource['kind'])}_scale"
    opts = {
        'body': {"spec": {'replicas': replicas}},
        'namespace': namespace,
        'name': name}
    if dry_run:
        opts['dry_run'] = 'All'
    return _api_call(
        'AppsV1Api', 'patch', ftn, **opts)


def get(obj: str, name: str = None, namespace: str = None,
        labels: str = None, all_namespaces: bool = False, ) -> dict:
    """Get or list resource(s) (similar to 'kubectl get')
    :param obj: resource type
    :param name: resource name
    :param namespace: namespace
    :param labels: kubernetes labels
    :param all_namespaces: scope where the resource must be gotten from
    :returns: data similar to 'kubectl get' in JSON format
    :raises exceptions.KubectlMethodException: if the resource cannot be 'gotten'"""
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


def delete(obj: str, name: str, namespace: str = None, dry_run: bool = False) -> dict:
    """Delete a resource (similar to 'kubectl delete')
    :param obj: resource type
    :param name: resource name
    :param namespace: namespace
    :param dry_run: dry-run
    :returns: data similar to 'kubectl delete' in JSON format
    :raises exceptions.KubectlMethodException: if the resource cannot be 'deleted'"""
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
    if dry_run:
        opts['dry_run'] = 'All'
    return _api_call(resource['api']['name'], 'delete', ftn, **opts)


def create(obj: str, name: str = None, namespace: str = None,
           body: dict = None, dry_run: bool = False) -> dict:
    """Create a resource (similar to 'kubectl create')
    :param obj: resource type
    :param name: resource name
    :param namespace: namespace
    :param body: kubernetes manifest body (overrides name and namespace)
    :param dry_run: dry-run
    :returns: data similar to 'kubectl create' in JSON format
    :raises exceptions.KubectlMethodException: if the resource cannot be 'created'"""
    body = body or {}
    namespace = namespace or 'default'
    if 'metadata' not in body:
        body['metadata'] = {}
    if name is not None and 'name' not in body['metadata']:
        body['metadata']['name'] = name
    if 'name' not in body['metadata']:
        raise exceptions.KubectlResourceNameException
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
    if dry_run:
        opts['dry_run'] = 'All'
    return _api_call(resource['api']['name'], 'create', ftn, **opts)


def patch(obj: str, name: str = None, namespace: str = None,
          body: dict = None, dry_run: bool = False) -> dict:
    """Patch a resource (similar to 'kubectl patch')
    :param obj: resource type
    :param name: resource name
    :param namespace: namespace
    :param body: kubernetes manifest body (overrides name and namespace)
    :param dry_run: dry-run
    :returns: data similar to 'kubectl patch' in JSON format
    :raises exceptions.KubectlMethodException: if the resource cannot be 'patched'"""
    body = body or {}
    namespace = namespace or 'default'
    if 'metadata' not in body:
        body['metadata'] = {}
    if name is not None and 'name' not in body['metadata']:
        body['metadata']['name'] = name
    if 'name' not in body['metadata']:
        raise exceptions.KubectlResourceNameException
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
    if dry_run:
        opts['dry_run'] = 'All'
    return _api_call(resource['api']['name'], 'patch', ftn, **opts)


def run(name: str, image: str, namespace: str = None, annotations: dict = None,
        labels: dict = None, env: dict = None, restart: str = 'Always') -> dict:
    """Create a pod (similar to 'kubectl run')
    :param obj: resource type
    :param image: resource name
    :param namespace: namespace
    :param annotations: annotations
    :param labels: labels
    :param env: environment variables
    :param restart: pod Restart policy
    :returns: data similar to 'kubectl create po' in JSON format"""
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
             overwrite: bool = False, dry_run: bool = False,
             **annotations) -> dict:
    """Annotate a resource (similar to 'kubectl annotate')
    :param obj: resource type
    :param image: resource name
    :param namespace: namespace
    :param annotations: annotations
    :param overwrite: Allow to overwrite existing annotations
    :returns: data similar to 'kubectl annotate' in JSON format"""
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
    return patch(obj, name, namespace, body, dry_run=dry_run)


def logs(name: str, namespace: str = None, container: str = None) -> str:
    """Get a pod logs (similar to 'kubectl logs')
    :param name: pod name
    :param namespace: namespace
    :param container: container
    :returns: data similar to 'kubectl logs' as a string"""
    namespace = namespace or 'default'
    api = kubernetes.client.CoreV1Api()
    resp = api.read_namespaced_pod(name=name, namespace=namespace).to_dict()
    if container is None:
        container = resp['spec']['containers'][0]['name']
    else:
        containers = []
        if resp['spec']['containers']:
            containers += [ctn['name'] for ctn in resp['spec']['containers']]
        if resp['spec']['init_containers']:
            containers += [ctn['name'] for ctn in resp['spec']['init_containers']]
        if container not in containers:
            raise exceptions.KubectlInvalidContainerException(name, namespace, container)
    return api.read_namespaced_pod_log(
        name,
        namespace,
        container=container)


def apply(body: dict, dry_run: bool = False) -> dict:
    """Create/Update a resource (similar to 'kubectl apply')
    :param body: kubenetes manifest data in JSON format
    :param dry_run: dry-run
    :returns: data similar to 'kubectl apply' in JSON format"""
    name = body['metadata']['name']
    namespace = body['metadata'].get('namespace', None)
    obj = body['kind']
    if get(obj, name, namespace) == {}:
        return create(obj, name, namespace, body, dry_run=dry_run)
    return patch(obj, name, namespace, body, dry_run=dry_run)


def top(obj: str, namespace: str = None, all_namespaces: bool = False) -> dict:
    """Get metrics from pods or nodes (similar to 'kubectl top')
    :param obj: resource type
    :param namespace: namespace
    :param all_namespaces: scope where the resource must be gotten from
    :returns: data similar to 'kubectl top' in JSON format
    :raises exceptions.KubectlBaseException: if the resource is neither pod nor nodes"""
    if obj not in ('pod', 'pods', 'node', 'nodes'):
        raise exceptions.KubectlBaseException(f'error: unknown command "{obj}"')
    obj = 'podmetrics' if obj in ('pod', 'pods') else 'nodemetrics'
    return get(obj, namespace=namespace, all_namespaces=all_namespaces)


# pylint: disable=redefined-builtin
def exec(name: str, command: list, namespace: str = None, container: str = None) -> str:
    """Execute a command in a pod (similar to 'kubectl exec')
    :param name: pod name
    :param command: command to execute
    :param namespace: namespace
    :param container: container
    :returns: command execution return value
    :raises exceptions.KubectlInvalidContainerException: if the container doesnt exist"""
    namespace = namespace or 'default'
    api = kubernetes.client.CoreV1Api()
    resp = api.read_namespaced_pod(name=name, namespace=namespace).to_dict()
    if container is None:
        container = resp['spec']['containers'][0]['name']
    else:
        if container not in [ctn['name'] for ctn in resp['spec']['containers']]:
            raise exceptions.KubectlInvalidContainerException(name, namespace, container)
    resp = kubernetes.stream.stream(
        api.connect_get_namespaced_pod_exec,
        name,
        namespace,
        container=container,
        command=command,
        stderr=True, stdin=False,
        stdout=True, tty=False)
    return resp


def cp(source: str, destination: str,
       namespace: str = None, container: str = None) -> bool:
    """Copy a file/directory from/to a pod (similar to 'kubectl cp')
    :param source: source (pod:path if remote)
    :param destination: destination (pod:path if remote)
    :param namespace: namespace
    :param container: container
    :returns: success (or not) boolean
    :raises exceptions.KubectlInvalidContainerException: if the container doesnt exist"""
    if len(source.split(':')) > 1 and len(destination.split(':')) > 1:
        raise exceptions.KubectlBaseException(
            'error: one of src or dest must be a local file specification')
    if len(source.split(':')) == 1 and len(destination.split(':')) == 1:
        raise exceptions.KubectlBaseException(
            'error: one of src or dest must be a remote file specification')
    namespace = namespace or 'default'
    api = kubernetes.client.CoreV1Api()
    if len(destination.split(':')) > 1:
        pod_name, remote_path = destination.split(':', 1)
        container = _find_container(pod_name, namespace, container)
        command = ['tar', 'xf', '-', '-C', remote_path]
        resp = kubernetes.stream.stream(
            api.connect_get_namespaced_pod_exec,
            pod_name,
            namespace,
            container=container,
            command=command,
            stderr=True, stdin=True,
            stdout=True, tty=False,
            _preload_content=False)

        with tempfile.TemporaryFile() as tar_buffer:
            with tarfile.open(fileobj=tar_buffer, mode='w') as tar:
                for source_file in glob.glob(source):
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
        pod_name, remote_path = source.split(':', 1)
        container = _find_container(pod_name, namespace, container)
        command = ['tar', 'cf', '-', remote_path]
        resp = kubernetes.stream.stream(
            api.connect_get_namespaced_pod_exec,
            pod_name,
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
                    if os.path.isdir(destination):
                        local_file = os.path.join(
                            destination, os.path.basename(member.name))
                    else:
                        local_file = destination
                    tar.makefile(member, local_file)
    return True


load_kubeconfig = connect
