"""Kubectl helper exceptions"""


class KubectlBaseException(ValueError):
    """Base kubectl exceptions. Catch it all"""
    def __init__(self, message):
        super().__init__(message)


class KubectlConfigException(KubectlBaseException):
    """Raised when the config cannot be loaded"""


class KubectlMethodException(KubectlBaseException):
    """Raised when a resource is not allowed"""
    def __init__(self):
        super().__init__(
            'Error from server (MethodNotAllowed): '
            'the server does not allow this method on the requested resource')


class KubectlResourceNameException(KubectlBaseException):
    """Raised when the resource name is absent"""
    def __init__(self):
        super().__init__(
            'error: resource(s) were provided, but no name was specified')


class KubectlResourceTypeException(KubectlBaseException):
    """Raised when the resource type is absent"""
    def __init__(self, arg):
        self.type = arg
        super().__init__(
            f'error: the server doesn\'t have a resource type "{arg}"')


class KubectlResourceNotFoundException(KubectlBaseException):
    """Raised when the resource cannot be found"""
    def __init__(self):
        super().__init__('the server could not find the requested resource')


class KubectlInvalidContainerException(KubectlBaseException):
    """Raised when the container name is incorrect"""
    def __init__(self, pod, namespace, container):
        self.pod = pod
        self.container = container
        self.namespace = namespace
        super().__init__(
                'Error from server (BadRequest): '
                f'container {container} is not valid for pod {pod}')
