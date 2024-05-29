"""
Kubectl helpers for python-kubernetes
That bunch of functions mimic kubectl behaviour and options
"""

import os.path
import sys
import atexit
import tarfile
import re
import select
import json
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


def _read_bytes_from_wsclient(
        ws_client: kubernetes.stream.ws_client.WSClient,
        timeout: int = 0) -> (bytes, bytes, bool):
    if not ws_client.sock.connected:
        # pylint: disable=protected-access
        ws_client._connected = False
    if not ws_client.is_open():
        return None, None, True
    stdout_bytes = None
    stderr_bytes = None
    r, _, _ = select.select(
        (ws_client.sock.sock, ), (), (), timeout)
    if r:
        op_code, frame = ws_client.sock.recv_data_frame(True)
        if op_code == 0x8:
            # pylint: disable=protected-access
            ws_client._connected = False
        elif op_code in (0x1, 0x2):
            data = frame.data
            if len(data) > 1:
                channel = data[0]
                data = data[1:]
                if data:
                    if channel == kubernetes.stream.ws_client.STDOUT_CHANNEL:
                        stdout_bytes = data
                    elif channel == kubernetes.stream.ws_client.STDERR_CHANNEL:
                        stderr_bytes = data
    return stdout_bytes, stderr_bytes, not ws_client.is_open()


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
    containers = []
    resp = api.read_namespaced_pod(name=name, namespace=namespace).to_dict()
    if resp['spec']['containers']:
        containers += [ctn['name'] for ctn in resp['spec']['containers']]
    if resp['spec'].get('init_containers'):
        containers += [ctn['name'] for ctn in resp['spec']['init_containers']]
    if container is None:
        if 'annotations' in resp['metadata'] and \
                resp['metadata']['annotations'] and \
                'kubectl.kubernetes.io/default-container' in \
                resp['metadata']['annotations']:
            container = resp['metadata']['annotations'][
                'kubectl.kubernetes.io/default-container']
        else:
            container = containers[0]
    if container not in containers:
        raise exceptions.KubectlInvalidContainerException(name, namespace, container)
    return container


def connect(host: str = None, api_key: str = None,
            certificate: str = None, context: str = None) -> str:
    """Create configuration so python-kubernetes can access resources.
    With no arguments, Try to get config from ~/.kube/config or KUBECONFIG
    If set, certificate parameter is not Base64-encoded.
    If unset, the SSL check is disabled
    :param host: Kubernetes server URL
    :param api_key: Kubernetes server API token
    :param certificate: Kubernetes server SSL certificate
    :param context: context to use if local config file is used (default: current one)
    :returns: K8s server URL where the client is connected to
    :raises exceptions.KubectlConfigException: if the connection fails"""
    # pylint: disable=global-statement
    global _temp_files
    if not host:
        try:
            kubernetes.config.load_kube_config(context=context)
        except kubernetes.config.config_exception.ConfigException as e:
            if context is not None:
                raise exceptions.KubectlConfigException(str(e)) from e
            try:
                kubernetes.config.load_incluster_config()
            except kubernetes.config.config_exception.ConfigException:
                raise exceptions.KubectlConfigException(str(e)) from e
    else:
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
    # pylint: disable=protected-access
    return kubernetes.client.Configuration._default.host


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
        labels: dict = None, env: dict = None, restart: str = 'Always',
        command: list = None) -> dict:
    """Create a pod (similar to 'kubectl run')
    :param obj: resource type
    :param image: resource name
    :param namespace: namespace
    :param annotations: annotations
    :param labels: labels
    :param env: environment variables
    :param restart: pod Restart policy
    :param command: command list to execute
    :returns: data similar to 'kubectl create po' in JSON format"""
    annotations = annotations or {}
    env = env or {}
    namespace = namespace or 'default'
    labels = labels or {'run': name}
    command = command or []
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
    if command:
        body['spec']['containers'][0]['command'] = command
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


def logs(name: str, namespace: str = None, container: str = None,
         follow: bool = False) -> urllib3.response.HTTPResponse:
    """Get a pod logs (similar to 'kubectl logs')
    :param name: pod name
    :param namespace: namespace
    :param container: container
    :param follow: does the generator waits for additional logs
    :returns: HTTPReponse generator
    :raises exceptions.KubectlInvalidContainerException: if the container doesnt exist
    :raises exceptions.KubectlBaseException: if the pod is not ready"""
    namespace = namespace or 'default'
    api = kubernetes.client.CoreV1Api()
    container = _find_container(name, namespace, container)
    try:
        return api.read_namespaced_pod_log(
            name,
            namespace,
            container=container,
            follow=follow,
            _preload_content=False)
    except kubernetes.client.exceptions.ApiException as err:
        body = err.body
        try:
            body = json.loads(body)['message']
        except (ValueError, AttributeError):
            pass
        raise exceptions.KubectlBaseException(body) from err


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
def exec(name: str, command: list, namespace: str = None,
         container: str = None, stdout: bool = False,
         stderr: bool = False) -> (bool, str):
    """Execute a command in a pod (similar to 'kubectl exec')
    :param name: pod name
    :param command: command to execute
    :param namespace: namespace
    :param container: container
    :param stdout: stream stdout during execution
    :param stderr: stream stderr during execution
    :returns: list of command execution exit code and return value
    :raises exceptions.KubectlInvalidContainerException: if the container doesnt exist"""
    namespace = namespace or 'default'
    api = kubernetes.client.CoreV1Api()
    container = _find_container(name, namespace, container)
    resp = kubernetes.stream.stream(
        api.connect_get_namespaced_pod_exec,
        name,
        namespace,
        container=container,
        command=command,
        stderr=True, stdin=False,
        stdout=True, tty=False,
        _preload_content=False)
    while resp.is_open():
        resp.update(timeout=1)
        if resp.peek_stdout() and stdout is True:
            sys.stdout.write(resp.read_stdout())
        if resp.peek_stderr() and stderr is True:
            sys.stderr.write(resp.read_stderr())
    err = resp.read_channel(kubernetes.stream.ws_client.ERROR_CHANNEL)
    return json.loads(err)["status"] == "Success", ''.join(resp.read_all())


# pylint: disable=too-many-branches
def cp(source: str, destination: str,
       namespace: str = None, container: str = None) -> bool:
    """Copy a file/directory from/to a pod (similar to 'kubectl cp')
    :param source: source (pod:path if remote)
    :param destination: destination (pod:path if remote)
    :param namespace: namespace
    :param container: container
    :returns: success (or not) boolean
    :raises exceptions.KubectlInvalidContainerException: if the container doesnt exist
    :raises exceptions.KubectlBaseException: if both source and destination are remote
    :raises exceptions.KubectlBaseException: if both source and destination are local"""
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
        if remote_path.endswith('/'):
            remote_path = remote_path[:-1]
        if source.endswith('/'):
            source = source[:-1]
        container = _find_container(pod_name, namespace, container)
        if exec(pod_name, ["test", "-d", remote_path], namespace, container)[0] is True:
            _dest_path = os.path.join(remote_path, os.path.basename(source))
        else:
            _dest_path = remote_path
        command = ['tar', 'xf', '-', '-C', "/"]
        resp = kubernetes.stream.stream(
            api.connect_get_namespaced_pod_exec,
            pod_name,
            namespace,
            container=container,
            command=command,
            stderr=True, stdin=True,
            stdout=True, tty=False,
            _preload_content=False)

        _files = []
        if os.path.isdir(source):
            for _dir, _, _file_list in os.walk(source):
                _files += [
                    (os.path.join(_dir, _file), os.path.join(
                        _dest_path, _dir.replace(source, '.', 1), _file))
                    for _file in _file_list]
        else:
            _files = [(source, _dest_path)]
        with tempfile.TemporaryFile() as tar_buffer:
            with tarfile.open(fileobj=tar_buffer, mode='w') as tar:
                for _file in _files:
                    tar.add(_file[0], _file[1])

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
                    try:
                        c = c.decode()
                    except UnicodeDecodeError:
                        pass
                    resp.write_stdin(c)
                else:
                    break
            resp.close()
    else:
        pod_name, remote_path = source.split(':', 1)
        container = _find_container(pod_name, namespace, container)
        command = ['tar', 'cf', '-', remote_path]
        if exec(pod_name, ["test", "-d", remote_path], namespace, container)[0] is True:
            if not os.path.isdir(destination):
                os.mkdir(destination)
        resp = kubernetes.stream.stream(
            api.connect_get_namespaced_pod_exec,
            pod_name,
            namespace,
            container=container,
            command=command,
            stderr=True, stdin=False,
            stdout=True, tty=False,
            _preload_content=False)
        with tempfile.TemporaryFile() as tar_buffer:
            while True:
                # workaround to handle big binary files
                out, err, closed = _read_bytes_from_wsclient(resp)
                if out:
                    tar_buffer.write(out)
                if err:
                    print(f"STDERR: {err.decode()}")
                if closed:
                    break
            resp.close()
            tar_buffer.flush()
            tar_buffer.seek(0)
            if remote_path.startswith('/'):
                remote_path = remote_path[1:]
            with tarfile.open(fileobj=tar_buffer, mode='r:') as tar:
                if not tar.getmembers():
                    return False
                for member in tar.getmembers():
                    if os.path.isdir(destination):
                        local_file = os.path.join(
                            destination, member.name.replace(remote_path, '.', 1))
                        if member.isdir():
                            if not os.path.isdir(local_file):
                                os.mkdir(local_file)
                            continue
                    else:
                        local_file = destination

                    tar.makefile(member, local_file)
    return True


load_kubeconfig = connect
