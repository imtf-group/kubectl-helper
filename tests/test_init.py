import os
import sys
from unittest import mock
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__))))

import kubectl

class InitTests(unittest.TestCase):

    def setUp(self):
        pass

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
            with self.assertRaises(ValueError):
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
            with self.assertRaises(ValueError):
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
            with self.assertRaises(ValueError):
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
            with self.assertRaises(ValueError):
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
            with self.assertRaises(ValueError):
                kubectl.get("pod", "toto")

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
                body={'spec': {'serviceAccountName': 'sa'}, 'metadata': {'name': 'toto'}, 'apiVersion': 'v1', 'kind': 'Pod'})

    def test_patch_pod_wrong_verb(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'Pod', 'name': 'pods',
                'namespaced': True, 'short_names': ['po'],
                'verbs': ['create', 'list']}]
        }
        with mock.patch("kubernetes.client", m):
            with self.assertRaises(ValueError):
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
                body={'spec': {'serviceAccountName': 'sa'}, 'metadata': {'name': 'toto'}, 'apiVersion': 'v1', 'kind': 'Pod'})

    def test_create_pod_wrong_verb(self):
        m = mock.Mock()
        m.CoreV1Api.return_value.get_api_resources.return_value.to_dict.return_value = {
            'resources': [{
                'kind': 'Pod', 'name': 'pods',
                'namespaced': True, 'short_names': ['po'],
                'verbs': ['delete', 'list']}]
        }
        with mock.patch("kubernetes.client", m):
            with self.assertRaises(ValueError):
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
                body={'kind': 'Pod', 'apiVersion': 'v1', 'metadata': {'name': 'nginx'}, 'spec': {'containers': [{'image': 'busybox'}]}},
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
                body={'kind': 'Pod', 'apiVersion': 'v1', 'metadata': {'name': 'nginx'}, 'spec': {'containers': [{'image': 'busybox'}]}},
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
            with self.assertRaises(ValueError):
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
                body={'kind': 'Pod', 'apiVersion': 'v1', 'metadata': {'name': 'nginx', 'annotations': {'owner': 'imtf', 'user': 'foobar'}}, 'spec': {}},
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
            with self.assertRaises(ValueError):
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
                body={'kind': 'Pod', 'apiVersion': 'v1', 'metadata': {'name': 'nginx', 'annotations': {'owner': 'imtf', 'user': 'bar'}}, 'spec': {}},
                namespace='default')


if __name__ == "__main__":
    unittest.main()
