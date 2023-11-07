# kubernetes 25.3.0

import os.path
import tarfile
import glob
import re
import kubernetes.client
import kubernetes.config
import kubernetes.stream
import tempfile

K8S_OBJECTS = [
    dict(name='Namespace', aliases=['ns'], apiVersion='v1', apiName='CoreV1Api', namespaced=False),
    dict(name='Pod', aliases=['po'], apiVersion='v1', apiName='CoreV1Api', namespaced=True),
    dict(name='Secret', aliases=[], apiVersion='v1', apiName='CoreV1Api', namespaced=True),
    dict(name='ConfigMap', aliases=['cm'], apiVersion='v1', apiName='CoreV1Api', namespaced=True),
    dict(name='Service', aliases=['svc'], apiVersion='v1', apiName='CoreV1Api', namespaced=True),
    dict(name='ServiceAccount', aliases=['sa'], apiVersion='v1', apiName='CoreV1Api', namespaced=True),
    dict(name='Deployment', aliases=['deploy'], apiVersion='apps/v1', apiName='AppsV1Api', namespaced=True),
    dict(name='StatefulSet', aliases=['sts'], apiVersion='apps/v1', apiName='AppsV1Api', namespaced=True),
    dict(name='DaemonSet', aliases=['ds'], apiVersion='apps/v1', apiName='AppsV1Api', namespaced=True),
    dict(name='ReplicaSet', aliases=['rs'], apiVersion='apps/v1', apiName='AppsV1Api', namespaced=True),
    dict(name='CronJob', aliases=['cj'], apiVersion='batch/v1', apiName='BatchV1Api', namespaced=True),
    dict(name='Job', aliases=[], apiVersion='batch/v1', apiName='BatchV1Api', namespaced=True),
    dict(name='Ingress', aliases=['ing'], apiVersion='networking.k8s.io/v1', apiName='NetworkingV1Api', namespaced=True)
]


def camel_to_snake(name):
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()


def load_kubeconfig():
    kubernetes.config.load_kube_config()


def _api_call(api_resource, verb, resource, **opts):
    ftn = "{0}_{1}".format(verb, resource)
    name = None
    if verb == 'list' and 'name' in opts:
        name = opts['name']
        del opts['name']
    api = getattr(kubernetes.client, api_resource)()
    try:
        objs = getattr(api, ftn)(**opts)
    except kubernetes.client.rest.ApiException as err:
        raise ValueError(err.body)
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
        else:
            plural = "{0}s".format(ftn.split('_', 2)[2])
            raise ValueError(f'Error from server (NotFound): {plural} "{name}" not found')
    else:
        if 'to_dict' in dir(objs):
            return objs.to_dict()
        else:
            return objs


def get(obj, name=None, namespace=None, labels=None):
    namespace = namespace or 'default'
    for k8s_obj in K8S_OBJECTS:
        if obj == k8s_obj['name'].lower() or \
                obj == k8s_obj['name'].lower() + 's' or \
                obj in k8s_obj['aliases']:
            ftn = camel_to_snake(k8s_obj['name'])
            opts = dict(label_selector=labels, name=name)
            if k8s_obj['namespaced'] is True:
                ftn = 'namespaced_' + ftn
                opts['namespace'] = namespace
            return _api_call(k8s_obj['apiName'], 'list', ftn, **opts)
    global_api = kubernetes.client.ApisApi()
    api = kubernetes.client.CustomObjectsApi()
    api_found = False
    for api_group in global_api.get_api_versions().to_dict()['groups']:
        for res in api.get_api_resources(
                api_group['name'],
                api_group['preferred_version']['version']).to_dict()['resources']:  
            if res['name'] == obj or (res['short_names'] and obj in res['short_names']):
                api_found = True
                break
        if api_found is True:
            break
    else:
        raise ValueError(f'error: the server doesn\'t have a resource type "{obj}"')
    if 'get' not in res['verbs']:
        raise ValueError(
            'Error from server (MethodNotAllowed): '
            'the server does not allow this method on the requested resource')
    return _api_call('CustomObjectsApi',
         'list', 'namespaced_custom_object',
         name=name,
         namespace=namespace,
         plural=res['name'],
         group=api_group['name'],
         version=api_group['preferred_version']['version'],
         label_selector=labels)


def delete(obj, name, namespace=None):
    namespace = namespace or 'default'
    for k8s_obj in K8S_OBJECTS:
        if obj == k8s_obj['name'].lower() or \
                obj == k8s_obj['name'].lower() + 's' or \
                obj in k8s_obj['aliases']:
            ftn = camel_to_snake(k8s_obj['name'])
            opts = dict(name=name)
            if k8s_obj['namespaced'] is True:
                ftn = 'namespaced_' + ftn
                opts['namespace'] = namespace
            return _api_call(k8s_obj['apiName'], 'delete', ftn, **opts)
    global_api = kubernetes.client.ApisApi()
    api = kubernetes.client.CustomObjectsApi()
    api_found = False
    for api_group in global_api.get_api_versions().to_dict()['groups']:
        for res in api.get_api_resources(
                api_group['name'],
                api_group['preferred_version']['version']).to_dict()['resources']:  
            if res['name'] == obj or (res['short_names'] and obj in res['short_names']):
                api_found = True
                break
        if api_found is True:
            break
    else:
        raise ValueError(f'error: the server doesn\'t have a resource type "{obj}"')
    if 'delete' not in res['verbs']:
        raise ValueError(
            'Error from server (MethodNotAllowed): '
            'the server does not allow this method on the requested resource')
    return _api_call('CustomObjectsApi',
         'delete', 'namespaced_custom_object',
         name=name,
         namespace=namespace,
         plural=res['name'],
         group=api_group['name'],
         version=api_group['preferred_version']['version'])


def create(obj, body, name=None, namespace=None):
    namespace = namespace or 'default'
    if name is not None:
        if 'metadata' not in body:
            body['metadata'] = {}
        body['metadata']['name'] = name
    for k8s_obj in K8S_OBJECTS:
        if obj == k8s_obj['name'].lower() or \
                obj == k8s_obj['name'].lower() + 's' or \
                obj in k8s_obj['aliases']:
            if 'apiVersion' not in body:
                body['apiVersion'] = k8s_obj['apiVersion']
            if 'kind' not in body:
                body['kind'] = k8s_obj['name']
            ftn = camel_to_snake(k8s_obj['name'])
            opts = dict(body=body)
            if k8s_obj['namespaced'] is True:
                ftn = 'namespaced_' + ftn
                opts['namespace'] = namespace
            return _api_call(k8s_obj['apiName'], 'create', ftn, **opts)
    global_api = kubernetes.client.ApisApi()
    api = kubernetes.client.CustomObjectsApi()
    api_found = False
    for api_group in global_api.get_api_versions().to_dict()['groups']:
        for res in api.get_api_resources(
                api_group['name'],
                api_group['preferred_version']['version']).to_dict()['resources']:  
            if res['name'] == obj or (res['short_names'] and obj in res['short_names']):
                api_found = True
                break
        if api_found is True:
            break
    else:
        raise ValueError(f'error: the server doesn\'t have a resource type "{obj}"')
    if 'create' not in res['verbs']:
        raise ValueError(
            'Error from server (MethodNotAllowed): '
            'the server does not allow this method on the requested resource')
    if 'apiVersion' not in body:
        body['apiVersion'] = api_group['preferred_version']['group_version']
    if 'kind' not in body:
        body['kind'] = res['kind']
    return _api_call('CustomObjectsApi',
         'create', 'namespaced_custom_object',
         namespace=namespace,
         plural=res['name'],
         group=api_group['name'],
         version=api_group['preferred_version']['version'],
         body=body)


def run(name, image, namespace=None, annotations={}, labels={}, env={}, restart='Always'):
    namespace = namespace or 'default'
    labels = labels or {'run': name}
    body = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"labels": labels, "annotations": annotations, "name": name},
        "spec": {"restartPolicy": restart, "containers": [{"image": image, "name": name}]}}
    envs = [{"name": k, "value": v} for k, v in env.items()]
    body['spec']['containers'][0]['env'] = envs
    return _api_call('CoreV1Api', 'create', 'namespaced_pod', namespace=namespace, body=body)


def logs(name: str, namespace: str = None, container: str = None) -> str:
    namespace = namespace or 'default'
    api = kubernetes.client.CoreV1Api()
    resp = api.read_namespaced_pod(name=name, namespace=namespace).to_dict()    
    if container is None:
        container = resp['spec']['containers'][0]['name']
    else:
        if container not in [ctn['name'] for ctn in resp['spec']['containers']]:
            raise ValueError(
                f'Error from server (BadRequest): '
                f'container {container} is not valid for pod {name}')
    return api.read_namespaced_pod_log(
        name,
        namespace,
        container=container)


def apply(obj, body, name=None, namespace=None):
    try:
        get(obj, name, namespace)
    except ValueError as err:
        if "not found" in err.args[0]:
            create(obj, body, name, namespace)

    namespace = namespace or 'default'
    if name is not None:
        if 'metadata' not in body:
            body['metadata'] = {}
        body['metadata']['name'] = name
    for k8s_obj in K8S_OBJECTS:
        if obj == k8s_obj['name'].lower() or \
                obj == k8s_obj['name'].lower() + 's' or \
                obj in k8s_obj['aliases']:
            if 'apiVersion' not in body:
                body['apiVersion'] = k8s_obj['apiVersion']
            if 'kind' not in body:
                body['kind'] = k8s_obj['name']
            ftn = camel_to_snake(k8s_obj['name'])
            opts = dict(name=name, body=body)
            if k8s_obj['namespaced'] is True:
                ftn = 'namespaced_' + ftn
                opts['namespace'] = namespace
            return _api_call(k8s_obj['apiName'], 'patch', ftn, **opts)
    global_api = kubernetes.client.ApisApi()
    api = kubernetes.client.CustomObjectsApi()
    api_found = False
    for api_group in global_api.get_api_versions().to_dict()['groups']:
        for res in api.get_api_resources(
                api_group['name'],
                api_group['preferred_version']['version']).to_dict()['resources']:  
            if res['name'] == obj or (res['short_names'] and obj in res['short_names']):
                api_found = True
                break
        if api_found is True:
            break
    else:
        raise ValueError(f'error: the server doesn\'t have a resource type "{obj}"')
    if 'patch' not in res['verbs']:
        raise ValueError(
            'Error from server (MethodNotAllowed): '
            'the server does not allow this method on the requested resource')
    if 'apiVersion' not in body:
        body['apiVersion'] = api_group['preferred_version']['group_version']
    if 'kind' not in body:
        body['kind'] = res['kind']
    return _api_call('CustomObjectsApi',
         'patch', 'namespaced_custom_object',
         name=name,
         namespace=namespace,
         plural=res['name'],
         group=api_group['name'],
         version=api_group['preferred_version']['version'],
         body=body)


def exec(name: str, command: list, namespace: str = None, container: str = None) -> str:
    namespace = namespace or 'default'
    api = kubernetes.client.CoreV1Api()
    resp = api.read_namespaced_pod(name=name, namespace=namespace).to_dict()    
    if container is None:
        container = resp['spec']['containers'][0]['name']
    else:
        if container not in [ctn['name'] for ctn in resp['spec']['containers']]:
            raise ValueError(
                f'Error from server (BadRequest): '
                f'container {container} is not valid for pod {name}')
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
        raise ValueError(
            'value for "mode" can only be "PULL" (from the container) '
            'or "PUSH" (to the container)')
    namespace = namespace or 'default'
    api = kubernetes.client.CoreV1Api()
    resp = api.read_namespaced_pod(name=name, namespace=namespace).to_dict()    
    if container is None:
        container = resp['spec']['containers'][0]['name']
    else:
        if container not in [ctn['name'] for ctn in resp['spec']['containers']]:
            raise ValueError(
                f'Error from server (BadRequest): '
                f'container {container} is not valid for pod {name}')
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
                    print("STDOUT: %s" % resp.read_stdout())
                if resp.peek_stderr():
                    print("STDERR: %s" % resp.read_stderr())
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
                    print("STDERR: %s" % resp.read_stderr())
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
