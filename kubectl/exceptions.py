class KubectlBaseException(ValueError):
    def __init__(self, message):
        super().__init__(message)


class KubectlMethodException(KubectlBaseException):
    def __init__(self):
        super().__init__(
            'Error from server (MethodNotAllowed): '
            'the server does not allow this method on the requested resource')


class KubectlTypeException(KubectlBaseException):
    def __init__(self, arg):
        self.type = arg
        super().__init__(
            f'error: the server doesn\'t have a resource type "{arg}"')


class KubectlResourceNotFoundException(KubectlBaseException):
    def __init__(self):
        super().__init__('the server could not find the requested resource')


class KubectlContainerNotFoundException(KubectlBaseException):
    def __init__(self, pod, namespace, container):
        self.pod = pod
        self.container = container
        self.namespace = namespace
        super().__init__(
                'Error from server (BadRequest): '
                f'container {container} is not valid for pod {pod}')
