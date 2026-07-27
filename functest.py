#!/usr/bin/env python

import os
import sys
import unittest
import uuid
import time
import kubectl

NAMESPACE = f"kubectl-helpers-test-{str(uuid.uuid4()).split('-')[0]}"
print(f"Test namespace: {NAMESPACE}")

class FuncTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        kubectl.connect()
        if not kubectl.get("namespace", NAMESPACE, ignore_not_found=True):
            kubectl.create("namespace", NAMESPACE)

    @classmethod
    def tearDownClass(cls):
        if kubectl.get("namespace", NAMESPACE, ignore_not_found=True):
            kubectl.delete("namespace", NAMESPACE)

    def test_get_exceptions(self):
        with self.assertRaises(kubectl.exceptions.KubectlBaseException):
            kubectl.get("pod", f"test-{uuid.uuid4()}", NAMESPACE)

    def test_get_notfound(self):
        self.assertFalse(kubectl.get("pod", f"test-{uuid.uuid4()}", NAMESPACE, ignore_not_found=True))

    def test_create(self):
        pod_name = f"test-{uuid.uuid4()}"
        body = {"spec": {"containers": [{"name": "test", "image": "busybox", "command": ["sh", "-c", "sleep 60"]}]}}
        kubectl.create("pod", pod_name, NAMESPACE, body=body)
        time.sleep(5)
        self.assertTrue(kubectl.get("pod", pod_name, NAMESPACE))

    def test_scale(self):
        pod_name = f"test-{uuid.uuid4()}"
        body = {
            "metadata": {"labels": {"app": pod_name}},
            "spec": {
            "replicas": 1, "selector": {
                "matchLabels": {"app": pod_name}
            },"template": {
                "metadata": {"labels": {"app": pod_name}},
                "spec": {"containers": [{"name": "busybox","image": "busybox", "command": ["sh", "-c", "sleep 60"]}]}}}}


        kubectl.create("deploy", pod_name, NAMESPACE, body=body)
        time.sleep(15)
        self.assertTrue(kubectl.get("pod", namespace=NAMESPACE, labels=f"app={pod_name}"))
        kubectl.scale("deploy", pod_name, namespace=NAMESPACE, replicas=0)
        time.sleep(30)
        self.assertIsNotNone(kubectl.get("pod", namespace=NAMESPACE, labels=f"app={pod_name}")[0]['status']['container_statuses'][0]['state']['terminated'])
        kubectl.scale("deploy", pod_name, namespace=NAMESPACE, replicas=1)
        time.sleep(15)
        self.assertTrue(kubectl.get("pod", namespace=NAMESPACE, labels=f"app={pod_name}"))
        
    def test_patch(self):
        pod_name = f"test-{uuid.uuid4()}"
        body = {
            "metadata": {"labels": {"app": pod_name}},
            "spec": {
            "replicas": 0, "selector": {
                "matchLabels": {"app": pod_name}
            },"template": {
                "metadata": {"labels": {"app": pod_name}},
                "spec": {"containers": [{"name": "busybox","image": "busybox", "command": ["sh", "-c", "sleep 60"]}]}}}}

        kubectl.create("deploy", pod_name, NAMESPACE, body=body)
        kubectl.patch("deploy", pod_name, namespace=NAMESPACE, body={"spec": {"replicas": 1}})
        time.sleep(15)
        self.assertTrue(kubectl.get("pod", namespace=NAMESPACE, labels=f"app={pod_name}"))
        
    def test_logs(self):
        pod_name = f"test-{uuid.uuid4()}"
        body = {
            "spec": {
                "containers": [{
                        "name": "test-1",
                        "image": "busybox",
                        "command": [
                            "sh",
                            "-c",
                            "I=0; while true; do echo $I; sleep 1; I=$((I+1)); done"
                        ]}],
                "restartPolicy": "Always",
                "dnsPolicy": "ClusterFirst"}}
        kubectl.create("pod", pod_name, NAMESPACE, body=body)
        time.sleep(20)
        r = kubectl.logs(pod_name, NAMESPACE).read().decode()
        for i, v in enumerate(r.split('\n')[:3]):
            self.assertEqual(i, int(v))
        
    def test_exec(self):
        pod_name = f"test-{uuid.uuid4()}"
        body = {"spec": {"containers": [{"name": "test", "image": "busybox", "command": ["sh", "-c", "sleep 60"]}]}}
        kubectl.create("pod", pod_name, NAMESPACE, body=body)
        time.sleep(5)
        b, r = kubectl.exec(pod_name, "hostname", NAMESPACE)
        self.assertTrue(b)
        self.assertEqual(pod_name, r.strip())

    def test_cp(self):
        pod_name = f"test-{uuid.uuid4()}"
        body = {"spec": {"containers": [{"name": "test", "image": "busybox", "command": ["sh", "-c", "sleep 300"]}]}}
        kubectl.create("pod", pod_name, NAMESPACE, body=body)
        time.sleep(5)
        b, r = kubectl.exec(pod_name, "cat etc/resolv.conf", NAMESPACE)
        self.assertTrue(b)
        kubectl.cp(f"{pod_name}:etc/resolv.conf", "myresolv", NAMESPACE)
        l = ""
        with open("myresolv", "r") as fd:
            l = fd.read()
        os.unlink("myresolv")
        self.assertEqual(l, r)


if __name__ == "__main__":
    unittest.main()
