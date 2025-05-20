# Table of Contents

* [kubectl](#kubectl)
  * [camel\_to\_snake](#kubectl.camel_to_snake)
  * [camel\_to\_snake\_dict](#kubectl.camel_to_snake_dict)
  * [snake\_to\_camel](#kubectl.snake_to_camel)
  * [snake\_to\_camel\_dict](#kubectl.snake_to_camel_dict)
  * [get\_contexts](#kubectl.get_contexts)
  * [connect](#kubectl.connect)
  * [api\_resources](#kubectl.api_resources)
  * [scale](#kubectl.scale)
  * [get](#kubectl.get)
  * [delete](#kubectl.delete)
  * [create](#kubectl.create)
  * [patch](#kubectl.patch)
  * [run](#kubectl.run)
  * [annotate](#kubectl.annotate)
  * [wait](#kubectl.wait)
  * [logs](#kubectl.logs)
  * [apply](#kubectl.apply)
  * [top](#kubectl.top)
  * [exec](#kubectl.exec)
  * [cp](#kubectl.cp)
* [kubectl.exceptions](#kubectl.exceptions)
  * [KubectlBaseException](#kubectl.exceptions.KubectlBaseException)
  * [KubectlConnectionException](#kubectl.exceptions.KubectlConnectionException)
  * [KubectlConfigException](#kubectl.exceptions.KubectlConfigException)
  * [KubectlMethodException](#kubectl.exceptions.KubectlMethodException)
  * [KubectlResourceNameException](#kubectl.exceptions.KubectlResourceNameException)
  * [KubectlResourceTypeException](#kubectl.exceptions.KubectlResourceTypeException)
  * [KubectlResourceNotFoundException](#kubectl.exceptions.KubectlResourceNotFoundException)
  * [KubectlInvalidContainerException](#kubectl.exceptions.KubectlInvalidContainerException)

<a id="kubectl"></a>

# kubectl

Kubectl helpers for python-kubernetes
That bunch of functions mimic kubectl behaviour and options

<a id="kubectl.camel_to_snake"></a>

#### camel\_to\_snake

```python
def camel_to_snake(name: str) -> str
```

Converts Camel-style string to Snake-style string

<a id="kubectl.camel_to_snake_dict"></a>

#### camel\_to\_snake\_dict

```python
def camel_to_snake_dict(body: dict) -> dict
```

Ensure fields are in Camel Case

<a id="kubectl.snake_to_camel"></a>

#### snake\_to\_camel

```python
def snake_to_camel(name: str) -> str
```

Converts Snake-style string to Camel-style string

<a id="kubectl.snake_to_camel_dict"></a>

#### snake\_to\_camel\_dict

```python
def snake_to_camel_dict(body: dict) -> dict
```

Ensure fields are in Camel Case

<a id="kubectl.get_contexts"></a>

#### get\_contexts

```python
def get_contexts() -> dict
```

List all the current contexts from ~/.kube/config or KUBECONFIG

**Returns**:

context dict

<a id="kubectl.connect"></a>

#### connect

```python
def connect(host: str = None,
            api_key: str = None,
            certificate: str = None,
            context: str = None) -> str
```

Create configuration so python-kubernetes can access resources.

With no arguments, Try to get config from ~/.kube/config or KUBECONFIG
If set, certificate parameter is not Base64-encoded.
If unset, the SSL check is disabled

**Arguments**:

- `host`: Kubernetes server URL
- `api_key`: Kubernetes server API token
- `certificate`: Kubernetes server SSL certificate
- `context`: context to use if local config file is used (default: current one)

**Raises**:

- `exceptions.KubectlConfigException`: if the connection fails

**Returns**:

used context

<a id="kubectl.api_resources"></a>

#### api\_resources

```python
def api_resources(obj: str = None) -> dict
```

From a resource name or alias, extract the API name
and version to use from api-resources

<a id="kubectl.scale"></a>

#### scale

```python
def scale(obj: str,
          name: str,
          namespace: str = None,
          replicas: int = 1,
          dry_run: bool = False) -> dict
```

Scale Apps resources

**Arguments**:

- `obj`: resource type
- `name`: resource name
- `namespace`: namespace
- `replicas`: number of expected replicas once scaled

**Raises**:

- `exceptions.KubectlResourceNotFoundException`: if not a Apps resource

**Returns**:

patch_namespaced_object_scale JSON

<a id="kubectl.get"></a>

#### get

```python
def get(obj: str,
        name: str = None,
        namespace: str = None,
        labels: str = None,
        all_namespaces: bool = False) -> dict
```

Get or list resource(s) (similar to 'kubectl get')

**Arguments**:

- `obj`: resource type
- `name`: resource name
- `namespace`: namespace
- `labels`: kubernetes labels
- `all_namespaces`: scope where the resource must be gotten from

**Raises**:

- `exceptions.KubectlMethodException`: if the resource cannot be 'gotten'

**Returns**:

data similar to 'kubectl get' in JSON format

<a id="kubectl.delete"></a>

#### delete

```python
def delete(obj: str,
           name: str,
           namespace: str = None,
           dry_run: bool = False) -> dict
```

Delete a resource (similar to 'kubectl delete')

**Arguments**:

- `obj`: resource type
- `name`: resource name
- `namespace`: namespace
- `dry_run`: dry-run

**Raises**:

- `exceptions.KubectlMethodException`: if the resource cannot be 'deleted'

**Returns**:

data similar to 'kubectl delete' in JSON format

<a id="kubectl.create"></a>

#### create

```python
def create(obj: str,
           name: str = None,
           namespace: str = None,
           body: dict = None,
           dry_run: bool = False) -> dict
```

Create a resource (similar to 'kubectl create')

**Arguments**:

- `obj`: resource type
- `name`: resource name
- `namespace`: namespace
- `body`: kubernetes manifest body (overrides name and namespace)
- `dry_run`: dry-run

**Raises**:

- `exceptions.KubectlMethodException`: if the resource cannot be 'created'

**Returns**:

data similar to 'kubectl create' in JSON format

<a id="kubectl.patch"></a>

#### patch

```python
def patch(obj: str,
          name: str = None,
          namespace: str = None,
          body: dict = None,
          dry_run: bool = False) -> dict
```

Patch a resource (similar to 'kubectl patch')

**Arguments**:

- `obj`: resource type
- `name`: resource name
- `namespace`: namespace
- `body`: kubernetes manifest body (overrides name and namespace)
- `dry_run`: dry-run

**Raises**:

- `exceptions.KubectlMethodException`: if the resource cannot be 'patched'

**Returns**:

data similar to 'kubectl patch' in JSON format

<a id="kubectl.run"></a>

#### run

```python
def run(name: str,
        image: str,
        namespace: str = None,
        annotations: dict = None,
        labels: dict = None,
        env: dict = None,
        restart: str = 'Always',
        command: list = None) -> dict
```

Create a pod (similar to 'kubectl run')

**Arguments**:

- `obj`: resource type
- `image`: resource name
- `namespace`: namespace
- `annotations`: annotations
- `labels`: labels
- `env`: environment variables
- `restart`: pod Restart policy
- `command`: command list to execute

**Returns**:

data similar to 'kubectl create po' in JSON format

<a id="kubectl.annotate"></a>

#### annotate

```python
def annotate(obj: str,
             name: str,
             namespace: str = None,
             overwrite: bool = False,
             dry_run: bool = False,
             **annotations) -> dict
```

Annotate a resource (similar to 'kubectl annotate')

**Arguments**:

- `obj`: resource type
- `image`: resource name
- `namespace`: namespace
- `annotations`: annotations in key=value format (key=None for deletion)
- `overwrite`: Allow to overwrite existing annotations

**Raises**:

- `exceptions.KubectlBaseException`: if an annotation exists and overwrite=False
- `exceptions.KubectlBaseException`: no annotation are submitted

**Returns**:

data similar to 'kubectl annotate' in JSON format

<a id="kubectl.wait"></a>

#### wait

```python
def wait(obj: str,
         name: str,
         namespace: str = None,
         condition: str = None,
         timeout: int = 300) -> bool
```

Wait for a pod to be at a given state

**Arguments**:

- `obj`: resource type
- `name`: pod name
- `namespace`: namespace
- `condition`: condition in the form condition=status
- `timeout`: time limit to wait

**Raises**:

- `exceptions.KubectlBaseException`: if the timeout exceeeds

**Returns**:

bool

<a id="kubectl.logs"></a>

#### logs

```python
def logs(name: str,
         namespace: str = None,
         container: str = None,
         follow: bool = False) -> urllib3.response.HTTPResponse
```

Get a pod logs (similar to 'kubectl logs')

**Arguments**:

- `name`: pod name
- `namespace`: namespace
- `container`: container
- `follow`: does the generator waits for additional logs

**Raises**:

- `exceptions.KubectlInvalidContainerException`: if the container doesnt exist
- `exceptions.KubectlBaseException`: if the pod is not ready

**Returns**:

HTTPReponse generator

<a id="kubectl.apply"></a>

#### apply

```python
def apply(body: dict, dry_run: bool = False) -> dict
```

Create/Update a resource (similar to 'kubectl apply')

**Arguments**:

- `body`: kubenetes manifest data in JSON format
- `dry_run`: dry-run

**Returns**:

data similar to 'kubectl apply' in JSON format

<a id="kubectl.top"></a>

#### top

```python
def top(obj: str, namespace: str = None, all_namespaces: bool = False) -> dict
```

Get metrics from pods or nodes (similar to 'kubectl top')

**Arguments**:

- `obj`: resource type
- `namespace`: namespace
- `all_namespaces`: scope where the resource must be gotten from

**Raises**:

- `exceptions.KubectlBaseException`: if the resource is neither pod nor nodes

**Returns**:

data similar to 'kubectl top' in JSON format

<a id="kubectl.exec"></a>

#### exec

```python
def exec(name: str,
         command: list,
         namespace: str = None,
         container: str = None,
         stdout: bool = False,
         stderr: bool = False) -> (bool, str)
```

Execute a command in a pod (similar to 'kubectl exec')

**Arguments**:

- `name`: pod name
- `command`: command to execute
- `namespace`: namespace
- `container`: container
- `stdout`: stream stdout during execution
- `stderr`: stream stderr during execution

**Raises**:

- `exceptions.KubectlInvalidContainerException`: if the container doesnt exist

**Returns**:

list of command execution exit code and return value

<a id="kubectl.cp"></a>

#### cp

```python
def cp(source: str,
       destination: str,
       namespace: str = None,
       container: str = None) -> bool
```

Copy a file/directory from/to a pod (similar to 'kubectl cp')

**Arguments**:

- `source`: source (pod:path if remote)
- `destination`: destination (pod:path if remote)
- `namespace`: namespace
- `container`: container

**Raises**:

- `exceptions.KubectlInvalidContainerException`: if the container doesnt exist
- `exceptions.KubectlBaseException`: if both source and destination are remote
- `exceptions.KubectlBaseException`: if both source and destination are local

**Returns**:

success (or not) boolean

<a id="kubectl.exceptions"></a>

# kubectl.exceptions

Kubectl helper exceptions

<a id="kubectl.exceptions.KubectlBaseException"></a>

## KubectlBaseException Objects

```python
class KubectlBaseException(ValueError)
```

Base kubectl exceptions. Catch it all

<a id="kubectl.exceptions.KubectlConnectionException"></a>

## KubectlConnectionException Objects

```python
class KubectlConnectionException(ValueError)
```

Raised when the K8s server cannot be reached

<a id="kubectl.exceptions.KubectlConfigException"></a>

## KubectlConfigException Objects

```python
class KubectlConfigException(KubectlBaseException)
```

Raised when the config cannot be loaded

<a id="kubectl.exceptions.KubectlMethodException"></a>

## KubectlMethodException Objects

```python
class KubectlMethodException(KubectlBaseException)
```

Raised when a resource is not allowed

<a id="kubectl.exceptions.KubectlResourceNameException"></a>

## KubectlResourceNameException Objects

```python
class KubectlResourceNameException(KubectlBaseException)
```

Raised when the resource name is absent

<a id="kubectl.exceptions.KubectlResourceTypeException"></a>

## KubectlResourceTypeException Objects

```python
class KubectlResourceTypeException(KubectlBaseException)
```

Raised when the resource type is absent

<a id="kubectl.exceptions.KubectlResourceNotFoundException"></a>

## KubectlResourceNotFoundException Objects

```python
class KubectlResourceNotFoundException(KubectlBaseException)
```

Raised when the resource cannot be found

<a id="kubectl.exceptions.KubectlInvalidContainerException"></a>

## KubectlInvalidContainerException Objects

```python
class KubectlInvalidContainerException(KubectlBaseException)
```

Raised when the container name is incorrect

Generated with: `pydoc-markdown -m kubectl -m kubectl.exceptions -I $(pwd) --render-toc > README.md`
