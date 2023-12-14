import os
import sys
from unittest import mock
import unittest
import kubernetes.client

if os.environ.get("CI", "false") != "true":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__))))

import kubectl

class InitTests(unittest.TestCase):

    def setUp(self):
        kubernetes.client.Configuration._default = None

    def test_config_with_kubeconfig(self):
        print(f"CI={os.environ.get('CI', 'false')}")
        if os.environ.get("CI", "false") != "true":
            self.assertIsNone(kubernetes.client.Configuration._default)
            kubectl.load_kubeconfig()
            self.assertIsNotNone(kubernetes.client.Configuration._default)

    def test_config_with_certificate(self):
        self.assertIsNone(kubernetes.client.Configuration._default)
        kubectl.load_kubeconfig("http://localhost", "APIKEY", b"CERTIFICATE")
        self.assertEqual(kubernetes.client.Configuration._default.host, "http://localhost")
        self.assertEqual(
            kubernetes.client.Configuration._default.api_key,
            {'authorization': 'APIKEY'})
        self.assertTrue(kubernetes.client.Configuration._default.verify_ssl)
        with open(kubernetes.client.Configuration._default.ssl_ca_cert) as fd:
            self.assertEqual(fd.read(), "CERTIFICATE")

    def test_config_without_certificate(self):
        self.assertIsNone(kubernetes.client.Configuration._default)
        kubectl.load_kubeconfig("http://localhost", "APIKEY")
        self.assertEqual(kubernetes.client.Configuration._default.host, "http://localhost")
        self.assertEqual(
            kubernetes.client.Configuration._default.api_key,
            {'authorization': 'APIKEY'})
        self.assertFalse(kubernetes.client.Configuration._default.verify_ssl)
        self.assertIsNone(kubernetes.client.Configuration._default.ssl_ca_cert)

    def test_unknown_resource(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {'resources': []}
        m.ApisApi.return_value.get_api_versions.return_value.to_dict.return_value = {'groups': []}
        with mock.patch("kubernetes.client", m):
            with self.assertRaises(kubectl.exceptions.KubectlTypeException):
                kubectl._get_resource("imtf")

    def test_list_namespace(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'Namespace', 'name': 'namespaces',
                'namespaced': False, 'short_names': ['ns'],
                'verbs': ['get', 'list']}]
        }
        m.CoreV1Api.return_value.list_namespace.return_value = {'items': ['boo']}
        with mock.patch("kubernetes.client", m):
            self.assertEqual(kubectl.get("namespaces"), ["boo"])
            m.CoreV1Api().list_namespace.assert_called_once_with(label_selector=None)

    def test_list_namespace_wrong_verb(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'Namespace', 'name': 'namespaces',
                'namespaced': False, 'short_names': ['ns'],
                'verbs': ['create', 'delete', 'get']}]
        }
        m.CoreV1Api.return_value.list_namespace.return_value = {'items': ['boo']}
        with mock.patch("kubernetes.client", m):
            with self.assertRaises(kubectl.exceptions.KubectlBaseException):
                kubectl.get("namespaces")

    def test_get_pod(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'Pod', 'name': 'pods',
                'namespaced': True, 'short_names': ['po'],
                'verbs': ['get', 'list']}]
        }
        m.CoreV1Api.return_value.list_namespaced_pod.return_value = {'items': [{
            'metadata': {'name': 'foobar'},
            'metadata': {'name': 'toto'}}]}
        with mock.patch("kubernetes.client", m):
            self.assertEqual(kubectl.get("pod", "toto"), {'metadata': {'name': 'toto'}})
            m.CoreV1Api().list_namespaced_pod.assert_called_once_with(label_selector=None, namespace='default')

    def test_get_pod_wrong_verb(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'Pod', 'name': 'pods',
                'namespaced': True, 'short_names': ['po'],
                'verbs': ['create', 'list']}]
        }
        m.CoreV1Api.return_value.list_namespaced_pod.return_value = {'items': [
            {'metadata': {'name': 'foobar'}},
            {'metadata': {'name': 'toto'}}]}
        with mock.patch("kubernetes.client", m):
            with self.assertRaises(kubectl.exceptions.KubectlBaseException):
                kubectl.get("pod", "toto")

    def test_get_pod_with_namespace(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'Pod', 'name': 'pods',
                'namespaced': True, 'short_names': ['po'],
                'verbs': ['get', 'list']}]
        }
        m.CoreV1Api.return_value.list_namespaced_pod.return_value = {'items': [
            {'metadata': {'name': 'foobar'}},
            {'metadata': {'name': 'toto'}}]}
        with mock.patch("kubernetes.client", m):
            self.assertEqual(kubectl.get("pod", "toto", "myns"), {'metadata': {'name': 'toto'}})
            m.CoreV1Api().list_namespaced_pod.assert_called_once_with(label_selector=None, namespace='myns')

    def test_get_pod_with_all_namespaces(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'Pod', 'name': 'pods',
                'namespaced': True, 'short_names': ['po'],
                'verbs': ['get', 'list']}]
        }
        m.CoreV1Api.return_value.list_pod_for_all_namespaces.return_value = {'items': [
            {'metadata': {'name': 'foobar'}},
            {'metadata': {'name': 'toto'}}]}
        with mock.patch("kubernetes.client", m):
            self.assertEqual(
                kubectl.get("pod", labels="app=toto", all_namespaces=True),
                [{'metadata': {'name': 'foobar'}}, {'metadata': {'name': 'toto'}}])
            m.CoreV1Api().list_pod_for_all_namespaces.assert_called_once_with(label_selector="app=toto")

    def test_get_cluster_custom_resource(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {'resources': []}
        m.ApisApi.return_value.get_api_versions.return_value.to_dict.return_value = {'groups': [{
            'name': 'imtf.k8s.io',
            'preferred_version': {'version': 'v1', 'group_version': 'imtf.k8s.io/v1'}
        }]}
        m.CustomObjectsApi.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'ImtfInstance', 'name': 'imtfinstances',
                'namespaced': False, 'short_names': ['imtf'],
                'verbs': ['get', 'list']}]
        }
        m.CustomObjectsApi.return_value.list_cluster_custom_object.return_value = {'items': [{
            'metadata': {'name': 'sc1'},
            'metadata': {'name': 'sc2'}}]}
        with mock.patch("kubernetes.client", m):
            self.assertEqual(kubectl.get("imtf", "sc2"), {'metadata': {'name': 'sc2'}})
            m.CustomObjectsApi().list_cluster_custom_object.assert_called_once_with(
                label_selector=None,
                plural='imtfinstances',
                group='imtf.k8s.io',
                version='v1')

    def test_get_namespaced_custom_resource(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {'resources': []}
        m.ApisApi.return_value.get_api_versions.return_value.to_dict.return_value = {'groups': [{
            'name': 'imtf.k8s.io',
            'preferred_version': {'version': 'v1', 'group_version': 'imtf.k8s.io/v1'}
        }]}
        m.CustomObjectsApi.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'ImtfInstance', 'name': 'imtfinstances',
                'namespaced': True, 'short_names': ['imtf'],
                'verbs': ['get', 'list']}]
        }
        m.CustomObjectsApi.return_value.list_namespaced_custom_object.return_value = {'items': [{
            'metadata': {'name': 'sc1'},
            'metadata': {'name': 'sc2'}}]}
        with mock.patch("kubernetes.client", m):
            self.assertEqual(kubectl.get("imtf", "sc2", "current"), {'metadata': {'name': 'sc2'}})
            m.CustomObjectsApi().list_namespaced_custom_object.assert_called_once_with(
                label_selector=None,
                plural='imtfinstances',
                group='imtf.k8s.io',
                version='v1',
                namespace='current')

    def test_get_namespaced_custom_resource_for_all_namespaces(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {'resources': []}
        m.ApisApi.return_value.get_api_versions.return_value.to_dict.return_value = {'groups': [{
            'name': 'imtf.k8s.io',
            'preferred_version': {'version': 'v1', 'group_version': 'imtf.k8s.io/v1'}
        }]}
        m.CustomObjectsApi.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'ImtfInstance', 'name': 'imtfinstances',
                'namespaced': True, 'short_names': ['imtf'],
                'verbs': ['get', 'list']}]
        }
        m.CustomObjectsApi.return_value.list_cluster_custom_object.return_value = {'items': [{
            'metadata': {'name': 'sc1'},
            'metadata': {'name': 'sc2'}}]}
        with mock.patch("kubernetes.client", m):
            self.assertEqual(
                kubectl.get("imtf", all_namespaces=True),
                [{'metadata': {'name': 'sc1'}, 'metadata': {'name': 'sc2'}}])
            m.CustomObjectsApi().list_cluster_custom_object.assert_called_once_with(
                label_selector=None,
                plural='imtfinstances',
                group='imtf.k8s.io',
                version='v1')

    def test_scale_pod(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'Pod', 'name': 'pods',
                'namespaced': True, 'short_names': ['po'],
                'verbs': ['get', 'list']}]
        }
        with mock.patch("kubernetes.client", m):
            with self.assertRaises(kubectl.exceptions.KubectlBaseException):
                kubectl.scale("pod", "foobar", replicas=2)

    def test_scale_deployment_wrong_verb(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {'resources': []}
        m.ApisApi.return_value.get_api_versions.return_value.to_dict.return_value = {'groups': [{
            'name': 'apps',
            'preferred_version': {'version': 'v1', 'group_version': 'apps/v1'}
        }]}
        m.CustomObjectsApi.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'Deployment', 'name': 'deployments',
                'namespaced': True, 'short_names': ['deploy'],
                'verbs': ['get', 'list']}]
        }
        with mock.patch("kubernetes.client", m):
            with self.assertRaises(kubectl.exceptions.KubectlBaseException):
                kubectl.scale("deployment", "foobar", replicas=2)

    def test_scale_deployment(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {'resources': []}
        m.ApisApi.return_value.get_api_versions.return_value.to_dict.return_value = {'groups': [{
            'name': 'apps',
            'preferred_version': {'version': 'v1', 'group_version': 'apps/v1'}
        }]}
        m.CustomObjectsApi.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'Deployment', 'name': 'deployments',
                'namespaced': True, 'short_names': ['deploy'],
                'verbs': ['patch']}]
        }
        with mock.patch("kubernetes.client", m):
            kubectl.scale("deploy", "foobar", replicas=2)
            m.AppsV1Api().patch_namespaced_deployment_scale.assert_called_once_with(name='foobar', namespace='default', body={'spec': {'replicas': 2}})

    def test_delete_pod(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'Pod', 'name': 'pods',
                'namespaced': True, 'short_names': ['po'],
                'verbs': ['get', 'list', 'delete']}]
        }
        with mock.patch("kubernetes.client", m):
            kubectl.delete("pod", "toto")
            m.CoreV1Api().delete_namespaced_pod.assert_called_once_with(name='toto', namespace='default')

    def test_delete_pod_wrong_verb(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'Pod', 'name': 'pods',
                'namespaced': True, 'short_names': ['po'],
                'verbs': ['create', 'list']}]
        }
        with mock.patch("kubernetes.client", m):
            with self.assertRaises(kubectl.exceptions.KubectlBaseException):
                kubectl.delete("pod", "toto")

    def test_delete_cluster_custom_resource(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {'resources': []}
        m.ApisApi.return_value.get_api_versions.return_value.to_dict.return_value = {'groups': [{
            'name': 'imtf.k8s.io',
            'preferred_version': {'version': 'v1', 'group_version': 'imtf.k8s.io/v1'}
        }]}
        m.CustomObjectsApi.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'ImtfInstance', 'name': 'imtfinstances',
                'namespaced': False, 'short_names': ['imtf'],
                'verbs': ['get', 'list', 'delete']}]
        }
        with mock.patch("kubernetes.client", m):
            kubectl.delete("imtf", "sc2")
            m.CustomObjectsApi().delete_cluster_custom_object.assert_called_once_with(
                name="sc2",
                plural='imtfinstances',
                group='imtf.k8s.io',
                version='v1')

    def test_delete_namespaced_custom_resource(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {'resources': []}
        m.ApisApi.return_value.get_api_versions.return_value.to_dict.return_value = {'groups': [{
            'name': 'imtf.k8s.io',
            'preferred_version': {'version': 'v1', 'group_version': 'imtf.k8s.io/v1'}
        }]}
        m.CustomObjectsApi.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'ImtfInstance', 'name': 'imtfinstances',
                'namespaced': True, 'short_names': ['imtf'],
                'verbs': ['get', 'list', 'delete']}]
        }
        with mock.patch("kubernetes.client", m):
            kubectl.delete("imtf", "sc2", "current")
            m.CustomObjectsApi().delete_namespaced_custom_object.assert_called_once_with(
                name="sc2",
                plural='imtfinstances',
                group='imtf.k8s.io',
                version='v1',
                namespace='current')

    def test_patch_pod(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'Pod', 'name': 'pods',
                'namespaced': True, 'short_names': ['po'],
                'verbs': ['get', 'list', 'patch']}]
        }
        with mock.patch("kubernetes.client", m):
            kubectl.patch("pod", "toto", body={'spec': {'serviceAccountName': 'sa'}})
            m.CoreV1Api().patch_namespaced_pod.assert_called_once_with(
                name='toto',
                namespace='default',
                body={'spec': {'serviceAccountName': 'sa'}, 'metadata': {'namespace': 'default', 'name': 'toto'}, 'apiVersion': 'v1', 'kind': 'Pod'})

    def test_patch_pod_wrong_verb(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'Pod', 'name': 'pods',
                'namespaced': True, 'short_names': ['po'],
                'verbs': ['create', 'list']}]
        }
        with mock.patch("kubernetes.client", m):
            with self.assertRaises(kubectl.exceptions.KubectlBaseException):
                kubectl.patch("pod", "toto", body={'spec': {'serviceAccountName': 'sa'}})

    def test_patch_cluster_custom_resource(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {'resources': []}
        m.ApisApi.return_value.get_api_versions.return_value.to_dict.return_value = {'groups': [{
            'name': 'imtf.k8s.io',
            'preferred_version': {'version': 'v1', 'group_version': 'imtf.k8s.io/v1'}
        }]}
        m.CustomObjectsApi.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'ImtfInstance', 'name': 'imtfinstances',
                'namespaced': False, 'short_names': ['imtf'],
                'verbs': ['get', 'list', 'patch']}]
        }
        with mock.patch("kubernetes.client", m):
            kubectl.patch("imtf", "sc2", body={'rules': {'users': ['first']}})
            m.CustomObjectsApi().patch_cluster_custom_object.assert_called_once_with(
                name='sc2',
                body={'rules': {'users': ['first']}, 'metadata': {'name': 'sc2'}, 'apiVersion': 'imtf.k8s.io/v1', 'kind': 'ImtfInstance'},
                plural='imtfinstances',
                group='imtf.k8s.io',
                version='v1')

    def test_patch_namespaced_custom_resource(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {'resources': []}
        m.ApisApi.return_value.get_api_versions.return_value.to_dict.return_value = {'groups': [{
            'name': 'imtf.k8s.io',
            'preferred_version': {'version': 'v1', 'group_version': 'imtf.k8s.io/v1'}
        }]}
        m.CustomObjectsApi.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'ImtfInstance', 'name': 'imtfinstances',
                'namespaced': True, 'short_names': ['imtf'],
                'verbs': ['get', 'list', 'patch']}]
        }
        with mock.patch("kubernetes.client", m):
            kubectl.patch("imtf", "sc2", "current", body={'rules': {'users': ['first']}})
            m.CustomObjectsApi().patch_namespaced_custom_object.assert_called_once_with(
                name='sc2',
                body={'rules': {'users': ['first']}, 'metadata': {'name': 'sc2', 'namespace': 'current'}, 'apiVersion': 'imtf.k8s.io/v1', 'kind': 'ImtfInstance'},
                plural='imtfinstances',
                group='imtf.k8s.io',
                version='v1',
                namespace='current')

    def test_create_pod(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'Pod', 'name': 'pods',
                'namespaced': True, 'short_names': ['po'],
                'verbs': ['get', 'list', 'create']}]
        }
        with mock.patch("kubernetes.client", m):
            kubectl.create("pod", "toto", body={'spec': {'serviceAccountName': 'sa'}})
            m.CoreV1Api().create_namespaced_pod.assert_called_once_with(
                namespace='default',
                body={'spec': {'serviceAccountName': 'sa'}, 'metadata': {'namespace': 'default', 'name': 'toto'}, 'apiVersion': 'v1', 'kind': 'Pod'})

    def test_create_pod_wrong_verb(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'Pod', 'name': 'pods',
                'namespaced': True, 'short_names': ['po'],
                'verbs': ['delete', 'list']}]
        }
        with mock.patch("kubernetes.client", m):
            with self.assertRaises(kubectl.exceptions.KubectlBaseException):
                kubectl.create("pod", "toto", body={'spec': {'serviceAccountName': 'sa'}})

    def test_create_cluster_custom_resource(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {'resources': []}
        m.ApisApi.return_value.get_api_versions.return_value.to_dict.return_value = {'groups': [{
            'name': 'imtf.k8s.io',
            'preferred_version': {'version': 'v1', 'group_version': 'imtf.k8s.io/v1'}
        }]}
        m.CustomObjectsApi.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'ImtfInstance', 'name': 'imtfinstances',
                'namespaced': False, 'short_names': ['imtf'],
                'verbs': ['get', 'list', 'create']}]
        }
        with mock.patch("kubernetes.client", m):
            kubectl.create("imtf", "sc2", body={'rules': {'users': ['first']}})
            m.CustomObjectsApi().create_cluster_custom_object.assert_called_once_with(
                body={'rules': {'users': ['first']}, 'metadata': {'name': 'sc2'}, 'apiVersion': 'imtf.k8s.io/v1', 'kind': 'ImtfInstance'},
                plural='imtfinstances',
                group='imtf.k8s.io',
                version='v1')

    def test_create_namespaced_custom_resource(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {'resources': []}
        m.ApisApi.return_value.get_api_versions.return_value.to_dict.return_value = {'groups': [{
            'name': 'imtf.k8s.io',
            'preferred_version': {'version': 'v1', 'group_version': 'imtf.k8s.io/v1'}
        }]}
        m.CustomObjectsApi.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'ImtfInstance', 'name': 'imtfinstances',
                'namespaced': True, 'short_names': ['imtf'],
                'verbs': ['get', 'list', 'create']}]
        }
        with mock.patch("kubernetes.client", m):
            kubectl.create("imtf", "sc2", "current", body={'rules': {'users': ['first']}})
            m.CustomObjectsApi().create_namespaced_custom_object.assert_called_once_with(
                body={'rules': {'users': ['first']}, 'metadata': {'name': 'sc2', 'namespace': 'current'}, 'apiVersion': 'imtf.k8s.io/v1', 'kind': 'ImtfInstance'},
                plural='imtfinstances',
                group='imtf.k8s.io',
                version='v1',
                namespace='current')

    def test_apply_patch(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'Pod', 'name': 'pods',
                'namespaced': True, 'short_names': ['po'],
                'verbs': ['get', 'list', 'patch']}]
        }
        m.CoreV1Api().list_namespaced_pod.return_value = {'items': [
            {"kind": "Pod", "apiVersion": "v1", "metadata": {"name": "nginx"}, "spec": {"containers": [{"image": "nginx"}]}}]}
        with mock.patch("kubernetes.client", m):
            kubectl.apply(
                {"kind": "Pod", "apiVersion": "v1", "metadata": {"name": "nginx"}, "spec": {"containers": [{"image": "busybox"}]}})
            m.CoreV1Api().patch_namespaced_pod.assert_called_once_with(
                name='nginx',
                body={'kind': 'Pod', 'apiVersion': 'v1', 'metadata': {'name': 'nginx', 'namespace': 'default'}, 'spec': {'containers': [{'image': 'busybox'}]}},
                namespace='default')

    def test_apply_create(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'Pod', 'name': 'pods',
                'namespaced': True, 'short_names': ['po'],
                'verbs': ['get', 'list', 'create']}]
        }
        m.CoreV1Api().list_namespaced_pod.return_value = {'items': []}
        with mock.patch("kubernetes.client", m):
            kubectl.apply(
                {"kind": "Pod", "apiVersion": "v1", "metadata": {"name": "nginx"}, "spec": {"containers": [{"image": "busybox"}]}})
            m.CoreV1Api().create_namespaced_pod.assert_called_once_with(
                body={'kind': 'Pod', 'apiVersion': 'v1', 'metadata': {'name': 'nginx', 'namespace': 'default'}, 'spec': {'containers': [{'image': 'busybox'}]}},
                namespace='default')

    def test_apply_wrong_verb(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'Pod', 'name': 'pods',
                'namespaced': True, 'short_names': ['po'],
                'verbs': ['get', 'list', 'patch']}]
        }
        m.CoreV1Api().list_namespaced_pod.return_value = {'items': []}
        with mock.patch("kubernetes.client", m):
            with self.assertRaises(kubectl.exceptions.KubectlBaseException):
                kubectl.apply(
                    {"kind": "Pod", "apiVersion": "v1", "metadata": {"name": "nginx"}, "spec": {"containers": [{"image": "busybox"}]}})

    def test_annotate(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'Pod', 'name': 'pods',
                'namespaced': True, 'short_names': ['po'],
                'verbs': ['get', 'list', 'patch']}]
        }
        m.CoreV1Api().list_namespaced_pod.return_value = {'items': [
            {"kind": "Pod", "apiVersion": "v1", "metadata": {"name": "nginx"}, "spec": {}}]}
        with mock.patch("kubernetes.client", m):
            kubectl.annotate("pod", "nginx", owner="imtf", user="foobar")
            m.CoreV1Api().patch_namespaced_pod.assert_called_once_with(
                name='nginx',
                body={'kind': 'Pod', 'apiVersion': 'v1', 'metadata': {'name': 'nginx', 'namespace': 'default', 'annotations': {'owner': 'imtf', 'user': 'foobar'}}, 'spec': {}},
                namespace='default')

    def test_annotate_existing(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'Pod', 'name': 'pods',
                'namespaced': True, 'short_names': ['po'],
                'verbs': ['get', 'list', 'patch']}]
        }
        m.CoreV1Api().list_namespaced_pod.return_value = {'items': [
            {"kind": "Pod", "apiVersion": "v1", "metadata": {"name": "nginx", 'annotations': {'owner': 'imtf', 'user': 'foobar'}}, "spec": {}}]}
        with mock.patch("kubernetes.client", m):
            with self.assertRaises(kubectl.exceptions.KubectlBaseException):
                kubectl.annotate("pod", "nginx", owner="imtf", user="bar")

    def test_annotate_existing_overwrite(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'Pod', 'name': 'pods',
                'namespaced': True, 'short_names': ['po'],
                'verbs': ['get', 'list', 'patch']}]
        }
        m.CoreV1Api().list_namespaced_pod.return_value = {'items': [
            {"kind": "Pod", "apiVersion": "v1", "metadata": {"name": "nginx", 'annotations': {'owner': 'imtf', 'user': 'foobar'}}, "spec": {}}]}
        with mock.patch("kubernetes.client", m):
            kubectl.annotate("pod", "nginx", overwrite=True, owner="imtf", user="bar")
            m.CoreV1Api().patch_namespaced_pod.assert_called_once_with(
                name='nginx',
                body={'kind': 'Pod', 'apiVersion': 'v1', 'metadata': {'name': 'nginx', 'namespace': 'default', 'annotations': {'owner': 'imtf', 'user': 'bar'}}, 'spec': {}},
                namespace='default')

    def test_exec(self):
        mock_stream = mock.Mock()
        mock_stream.stream.return_value = '/usr\n/etc\n/bin\n'
        mock_client = mock.Mock()
        mock_client.CoreV1Api.return_value.read_namespaced_pod.return_value.to_dict.return_value = {
            'metadata': {
                'name': 'foobar',
                'namespace': 'current'},
            'spec': {
                'containers': [
                    {'name': 'first'},
                    {'name': 'second'}]}}
        mock_client.CoreV1Api.return_value.connect_get_namespaced_pod_exec = 'mock_function'
        with mock.patch("kubernetes.client", mock_client):
            with mock.patch("kubernetes.stream", mock_stream):
                self.assertEqual(kubectl.exec("foobar", "ls -d /", "current"), '/usr\n/etc\n/bin\n')
                mock_stream.stream.assert_called_once_with('mock_function', 'foobar', 'current', container='first', command='ls -d /', stderr=True, stdin=False, stdout=True, tty=False)

    def test_exec_wrong_container(self):
        mock_client = mock.Mock()
        mock_client.CoreV1Api.return_value.read_namespaced_pod.return_value.to_dict.return_value = {
            'metadata': {
                'name': 'foobar',
                'namespace': 'current'},
            'spec': {
                'containers': [
                    {'name': 'first'},
                    {'name': 'second'}]}}
        mock_client.CoreV1Api.return_value.connect_get_namespaced_pod_exec = 'mock_function'
        with mock.patch("kubernetes.client", mock_client):
            with self.assertRaises(kubectl.exceptions.KubectlContainerNotFoundException):
                kubectl.exec("foobar", "ls -d /", "current", "another")

    def test_run(self):
        m = mock.Mock()
        with mock.patch("kubernetes.client", m):
            kubectl.run("name", "image", annotations={'owner': 'imtf'}, env={'POD_NAME': 'podname'})
            m.CoreV1Api().create_namespaced_pod.assert_called_once_with(
                namespace='default',
                body={
                    'apiVersion': 'v1',
                    'kind': 'Pod',
                    'metadata': {
                        'labels': {'run': 'name'},
                        'annotations': {'owner': 'imtf'},
                        'namespace': 'default',
                        'name': 'name'},
                    'spec': {
                        'restartPolicy': 'Always',
                        'containers': [{
                            'image': 'image',
                            'name': 'name',
                            'env': [{'name': 'POD_NAME', 'value': 'podname'}]}]}})

    def test_logs(self):
        mock_client = mock.Mock()
        mock_client.CoreV1Api.return_value.read_namespaced_pod.return_value.to_dict.return_value = {
            'metadata': {
                'name': 'foobar',
                'namespace': 'current'},
            'spec': {
                'containers': [
                    {'name': 'first'},
                    {'name': 'second'}]}}
        mock_client.CoreV1Api.return_value.read_namespaced_pod_log.return_value = '/usr\n/etc\n/bin\n'
        with mock.patch("kubernetes.client", mock_client):
            self.assertEqual(kubectl.logs("foobar", "current"), '/usr\n/etc\n/bin\n')
            mock_client.CoreV1Api().read_namespaced_pod_log.assert_called_once_with('foobar', 'current', container='first')

    def test_logs_wrong_container(self):
        mock_client = mock.Mock()
        mock_client.CoreV1Api.return_value.read_namespaced_pod.return_value.to_dict.return_value = {
            'metadata': {
                'name': 'foobar',
                'namespace': 'current'},
            'spec': {
                'containers': [
                    {'name': 'first'},
                    {'name': 'second'}]}}
        with mock.patch("kubernetes.client", mock_client):
            with self.assertRaises(kubectl.exceptions.KubectlContainerNotFoundException):
                kubectl.logs("foobar", "current", "another")


    def test_top(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {'resources': []}
        m.ApisApi.return_value.get_api_versions.return_value.to_dict.return_value = {'groups': [{
            'name': 'metrics.k8s.io',
            'preferred_version': {'version': 'v1', 'group_version': 'metrics.k8s.io/v1'}
        }]}
        m.CustomObjectsApi.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'PodMetric', 'name': 'podmetrics',
                'namespaced': True, 'short_names': ['pod'],
                'verbs': ['get', 'list']}]
        }
        m.CustomObjectsApi.return_value.list_namespaced_custom_object.return_value = {'items': []}
        with mock.patch("kubernetes.client", m):
            kubectl.top("pods")
            m.CustomObjectsApi().list_namespaced_custom_object.assert_called_once_with(label_selector=None, plural='podmetrics', group='metrics.k8s.io', version='v1', namespace='default')

    def test_top_no_pods_or_nodes(self):
        with self.assertRaises(kubectl.exceptions.KubectlBaseException):
            kubectl.top("deployments")

    def test_cp_not_pull_or_push(self):
        with self.assertRaises(kubectl.exceptions.KubectlBaseException):
            kubectl.cp("nginx", "LOCALFILE", "/REMOTEFILE", mode='BOTH')

    def test_cp_wrong_container(self):
        mock_client = mock.Mock()
        mock_client.CoreV1Api.return_value.read_namespaced_pod.return_value.to_dict.return_value = {
            'metadata': {
                'name': 'foobar',
                'namespace': 'current'},
            'spec': {
                'containers': [
                    {'name': 'first'},
                    {'name': 'second'}]}}
        mock_client.CoreV1Api.return_value.connect_get_namespaced_pod_exec = 'mock_function'
        with mock.patch("kubernetes.client", mock_client):
            with self.assertRaises(kubectl.exceptions.KubectlContainerNotFoundException):
                kubectl.cp("nginx", "LOCALFILE", "/REMOTEFILE", mode='PUSH', container='another')


if __name__ == "__main__":
    unittest.main()
