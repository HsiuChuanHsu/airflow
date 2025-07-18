#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
from __future__ import annotations

import json
import random
import string
import textwrap
from io import StringIO
from unittest import mock

import paramiko
import pytest

from airflow import settings
from airflow.exceptions import AirflowException
from airflow.models import Connection
from airflow.providers.ssh.hooks.ssh import SSHHook

pytestmark = pytest.mark.db_test


HELLO_SERVER_CMD = """
import socket, sys
listener = socket.socket()
listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
listener.bind(('localhost', 2134))
listener.listen(1)
sys.stdout.write('ready')
sys.stdout.flush()
conn = listener.accept()[0]
conn.sendall(b'hello')
"""


def generate_key_string(pkey: paramiko.PKey, passphrase: str | None = None):
    with StringIO() as key_fh:
        pkey.write_private_key(key_fh, password=passphrase)
        key_fh.seek(0)
        key_str = key_fh.read()
    return key_str


def generate_host_key(pkey: paramiko.PKey):
    with StringIO() as key_fh:
        pkey.write_private_key(key_fh)
        key_fh.seek(0)
        key_obj = paramiko.RSAKey(file_obj=key_fh)
    return key_obj.get_base64()


TEST_PKEY = paramiko.RSAKey.generate(4096)
TEST_PRIVATE_KEY = generate_key_string(pkey=TEST_PKEY)
TEST_HOST_KEY = generate_host_key(pkey=TEST_PKEY)

TEST_PKEY_ECDSA = paramiko.ECDSAKey.generate()
TEST_PRIVATE_KEY_ECDSA = generate_key_string(pkey=TEST_PKEY_ECDSA)

TEST_TIMEOUT = 20
TEST_CONN_TIMEOUT = 30

TEST_CMD_TIMEOUT = 5
TEST_CMD_TIMEOUT_NOT_SET = "NOT SET"
TEST_CMD_TIMEOUT_EXTRA = 15

PASSPHRASE = "".join(random.choices(string.ascii_letters, k=10))
TEST_ENCRYPTED_PRIVATE_KEY = generate_key_string(pkey=TEST_PKEY, passphrase=PASSPHRASE)

TEST_DISABLED_ALGORITHMS = {"pubkeys": ["rsa-sha2-256", "rsa-sha2-512"]}

TEST_CIPHERS = ["aes128-ctr", "aes192-ctr", "aes256-ctr"]


class TestSSHHook:
    CONN_SSH_WITH_NO_EXTRA = "ssh_with_no_extra"
    CONN_SSH_WITH_PRIVATE_KEY_EXTRA = "ssh_with_private_key_extra"
    CONN_SSH_WITH_PRIVATE_KEY_ECDSA_EXTRA = "ssh_with_private_key_ecdsa_extra"
    CONN_SSH_WITH_PRIVATE_KEY_PASSPHRASE_EXTRA = "ssh_with_private_key_passphrase_extra"
    CONN_SSH_WITH_TIMEOUT_EXTRA = "ssh_with_timeout_extra"
    CONN_SSH_WITH_CONN_TIMEOUT_EXTRA = "ssh_with_conn_timeout_extra"
    CONN_SSH_WITH_CMD_TIMEOUT_EXTRA = "ssh_with_cmd_timeout_extra"
    CONN_SSH_WITH_NULL_CMD_TIMEOUT_EXTRA = "ssh_with_negative_cmd_timeout_extra"
    CONN_SSH_WITH_TIMEOUT_AND_CONN_TIMEOUT_EXTRA = "ssh_with_timeout_and_conn_timeout_extra"
    CONN_SSH_WITH_EXTRA = "ssh_with_extra"
    CONN_SSH_WITH_EXTRA_FALSE_LOOK_FOR_KEYS = "ssh_with_extra_false_look_for_keys"
    CONN_SSH_WITH_HOST_KEY_EXTRA = "ssh_with_host_key_extra"
    CONN_SSH_WITH_HOST_KEY_EXTRA_WITH_TYPE = "ssh_with_host_key_extra_with_type"
    CONN_SSH_WITH_HOST_KEY_AND_NO_HOST_KEY_CHECK_FALSE = "ssh_with_host_key_and_no_host_key_check_false"
    CONN_SSH_WITH_HOST_KEY_AND_NO_HOST_KEY_CHECK_TRUE = "ssh_with_host_key_and_no_host_key_check_true"
    CONN_SSH_WITH_NO_HOST_KEY_AND_NO_HOST_KEY_CHECK_FALSE = "ssh_with_no_host_key_and_no_host_key_check_false"
    CONN_SSH_WITH_NO_HOST_KEY_AND_NO_HOST_KEY_CHECK_TRUE = "ssh_with_no_host_key_and_no_host_key_check_true"
    CONN_SSH_WITH_HOST_KEY_AND_ALLOW_HOST_KEY_CHANGES_TRUE = (
        "ssh_with_host_key_and_allow_host_key_changes_true"
    )
    CONN_SSH_WITH_EXTRA_DISABLED_ALGORITHMS = "ssh_with_extra_disabled_algorithms"
    CONN_SSH_WITH_EXTRA_CIPHERS = "ssh_with_extra_ciphers"
    CONN_SSH_WITH_NO_HOST_KEY_CHECK_TRUE_AND_ALLOW_HOST_KEY_CHANGES_TRUE = (
        "ssh_with_no_host_key_check_true_and_allow_host_key_changes_true"
    )
    CONN_SSH_WITH_NO_HOST_KEY_CHECK_TRUE_AND_ALLOW_HOST_KEY_CHANGES_FALSE = (
        "ssh_with_no_host_key_check_true_and_allow_host_key_changes_false"
    )

    # TODO: Potential performance issue, converted setup_class to a setup_connections function level fixture
    @pytest.fixture(autouse=True)
    def setup_connections(self, create_connection_without_db):
        create_connection_without_db(
            Connection(
                conn_id=self.CONN_SSH_WITH_NO_EXTRA,
                host="localhost",
                conn_type="ssh",
                extra=None,
            )
        )
        create_connection_without_db(
            Connection(
                conn_id=self.CONN_SSH_WITH_EXTRA,
                host="localhost",
                conn_type="ssh",
                extra='{"compress" : true, "no_host_key_check" : "true", "allow_host_key_change": false}',
            )
        )
        create_connection_without_db(
            Connection(
                conn_id=self.CONN_SSH_WITH_EXTRA_FALSE_LOOK_FOR_KEYS,
                host="localhost",
                conn_type="ssh",
                extra='{"compress" : true, "no_host_key_check" : "true", '
                '"allow_host_key_change": false, "look_for_keys": false}',
            )
        )
        create_connection_without_db(
            Connection(
                conn_id=self.CONN_SSH_WITH_PRIVATE_KEY_EXTRA,
                host="localhost",
                conn_type="ssh",
                extra=json.dumps({"private_key": TEST_PRIVATE_KEY}),
            )
        )
        create_connection_without_db(
            Connection(
                conn_id=self.CONN_SSH_WITH_PRIVATE_KEY_PASSPHRASE_EXTRA,
                host="localhost",
                conn_type="ssh",
                extra=json.dumps(
                    {"private_key": TEST_ENCRYPTED_PRIVATE_KEY, "private_key_passphrase": PASSPHRASE}
                ),
            )
        )
        create_connection_without_db(
            Connection(
                conn_id=self.CONN_SSH_WITH_PRIVATE_KEY_ECDSA_EXTRA,
                host="localhost",
                conn_type="ssh",
                extra=json.dumps({"private_key": TEST_PRIVATE_KEY_ECDSA}),
            )
        )
        create_connection_without_db(
            Connection(
                conn_id=self.CONN_SSH_WITH_TIMEOUT_EXTRA,
                host="localhost",
                conn_type="ssh",
                extra=json.dumps({"timeout": TEST_TIMEOUT}),
            )
        )
        create_connection_without_db(
            Connection(
                conn_id=self.CONN_SSH_WITH_CONN_TIMEOUT_EXTRA,
                host="localhost",
                conn_type="ssh",
                extra=json.dumps({"conn_timeout": TEST_CONN_TIMEOUT}),
            )
        )
        create_connection_without_db(
            Connection(
                conn_id=self.CONN_SSH_WITH_TIMEOUT_AND_CONN_TIMEOUT_EXTRA,
                host="localhost",
                conn_type="ssh",
                extra=json.dumps({"conn_timeout": TEST_CONN_TIMEOUT, "timeout": TEST_TIMEOUT}),
            )
        )
        create_connection_without_db(
            Connection(
                conn_id=self.CONN_SSH_WITH_CMD_TIMEOUT_EXTRA,
                host="localhost",
                conn_type="ssh",
                extra=json.dumps({"cmd_timeout": TEST_CMD_TIMEOUT_EXTRA}),
            )
        )
        create_connection_without_db(
            Connection(
                conn_id=self.CONN_SSH_WITH_NULL_CMD_TIMEOUT_EXTRA,
                host="localhost",
                conn_type="ssh",
                extra=json.dumps({"cmd_timeout": None}),
            )
        )
        create_connection_without_db(
            Connection(
                conn_id=self.CONN_SSH_WITH_HOST_KEY_EXTRA,
                host="localhost",
                conn_type="ssh",
                extra=json.dumps({"private_key": TEST_PRIVATE_KEY, "host_key": TEST_HOST_KEY}),
            )
        )
        create_connection_without_db(
            Connection(
                conn_id=self.CONN_SSH_WITH_HOST_KEY_EXTRA_WITH_TYPE,
                host="localhost",
                conn_type="ssh",
                extra=json.dumps({"private_key": TEST_PRIVATE_KEY, "host_key": "ssh-rsa " + TEST_HOST_KEY}),
            )
        )
        create_connection_without_db(
            Connection(
                conn_id=self.CONN_SSH_WITH_HOST_KEY_AND_NO_HOST_KEY_CHECK_FALSE,
                host="remote_host",
                conn_type="ssh",
                extra=json.dumps(
                    {"private_key": TEST_PRIVATE_KEY, "host_key": TEST_HOST_KEY, "no_host_key_check": False}
                ),
            )
        )
        create_connection_without_db(
            Connection(
                conn_id=self.CONN_SSH_WITH_HOST_KEY_AND_NO_HOST_KEY_CHECK_TRUE,
                host="remote_host",
                conn_type="ssh",
                extra=json.dumps(
                    {"private_key": TEST_PRIVATE_KEY, "host_key": TEST_HOST_KEY, "no_host_key_check": True}
                ),
            )
        )
        create_connection_without_db(
            Connection(
                conn_id=self.CONN_SSH_WITH_NO_HOST_KEY_AND_NO_HOST_KEY_CHECK_FALSE,
                host="remote_host",
                conn_type="ssh",
                extra=json.dumps({"private_key": TEST_PRIVATE_KEY, "no_host_key_check": False}),
            )
        )
        create_connection_without_db(
            Connection(
                conn_id=self.CONN_SSH_WITH_NO_HOST_KEY_AND_NO_HOST_KEY_CHECK_TRUE,
                host="remote_host",
                conn_type="ssh",
                extra=json.dumps({"private_key": TEST_PRIVATE_KEY, "no_host_key_check": True}),
            )
        )
        create_connection_without_db(
            Connection(
                conn_id=self.CONN_SSH_WITH_HOST_KEY_AND_ALLOW_HOST_KEY_CHANGES_TRUE,
                host="remote_host",
                conn_type="ssh",
                extra=json.dumps(
                    {
                        "private_key": TEST_PRIVATE_KEY,
                        "host_key": TEST_HOST_KEY,
                        "allow_host_key_change": True,
                    }
                ),
            )
        )
        create_connection_without_db(
            Connection(
                conn_id=self.CONN_SSH_WITH_EXTRA_DISABLED_ALGORITHMS,
                host="localhost",
                conn_type="ssh",
                extra=json.dumps({"disabled_algorithms": TEST_DISABLED_ALGORITHMS}),
            )
        )
        create_connection_without_db(
            Connection(
                conn_id=self.CONN_SSH_WITH_EXTRA_CIPHERS,
                host="localhost",
                conn_type="ssh",
                extra=json.dumps({"ciphers": TEST_CIPHERS}),
            )
        )
        create_connection_without_db(
            Connection(
                conn_id=self.CONN_SSH_WITH_NO_HOST_KEY_CHECK_TRUE_AND_ALLOW_HOST_KEY_CHANGES_TRUE,
                host="remote_host",
                conn_type="ssh",
                extra=json.dumps({"no_host_key_check": True, "allow_host_key_change": True}),
            )
        )
        create_connection_without_db(
            Connection(
                conn_id=self.CONN_SSH_WITH_NO_HOST_KEY_CHECK_TRUE_AND_ALLOW_HOST_KEY_CHANGES_FALSE,
                host="remote_host",
                conn_type="ssh",
                extra=json.dumps({"no_host_key_check": True, "allow_host_key_change": False}),
            )
        )

    @mock.patch("airflow.providers.ssh.hooks.ssh.paramiko.SSHClient")
    def test_ssh_connection_with_password(self, ssh_mock):
        hook = SSHHook(
            remote_host="remote_host",
            port="port",
            username="username",
            password="password",
            conn_timeout=10,
            key_file="fake.file",
        )

        with hook.get_conn():
            ssh_mock.return_value.connect.assert_called_once_with(
                banner_timeout=30.0,
                hostname="remote_host",
                username="username",
                password="password",
                key_filename="fake.file",
                timeout=10,
                compress=True,
                port="port",
                sock=None,
                look_for_keys=True,
                auth_timeout=None,
            )

    @mock.patch("airflow.providers.ssh.hooks.ssh.paramiko.SSHClient")
    def test_ssh_connection_without_password(self, ssh_mock):
        hook = SSHHook(
            remote_host="remote_host", port="port", username="username", conn_timeout=10, key_file="fake.file"
        )

        with hook.get_conn():
            ssh_mock.return_value.connect.assert_called_once_with(
                banner_timeout=30.0,
                hostname="remote_host",
                username="username",
                key_filename="fake.file",
                timeout=10,
                compress=True,
                port="port",
                sock=None,
                look_for_keys=True,
                auth_timeout=None,
            )

    @mock.patch("airflow.providers.ssh.hooks.ssh.SSHTunnelForwarder")
    def test_tunnel_with_password(self, ssh_mock):
        hook = SSHHook(
            remote_host="remote_host",
            port="port",
            username="username",
            password="password",
            conn_timeout=10,
            key_file="fake.file",
        )

        with hook.get_tunnel(1234):
            ssh_mock.assert_called_once_with(
                "remote_host",
                ssh_port="port",
                ssh_username="username",
                ssh_password="password",
                ssh_pkey="fake.file",
                ssh_proxy=None,
                local_bind_address=("localhost",),
                remote_bind_address=("localhost", 1234),
                logger=hook.log,
            )

    @mock.patch("airflow.providers.ssh.hooks.ssh.SSHTunnelForwarder")
    def test_tunnel_without_password(self, ssh_mock):
        hook = SSHHook(
            remote_host="remote_host", port="port", username="username", conn_timeout=10, key_file="fake.file"
        )

        with hook.get_tunnel(1234):
            ssh_mock.assert_called_once_with(
                "remote_host",
                ssh_port="port",
                ssh_username="username",
                ssh_pkey="fake.file",
                ssh_proxy=None,
                local_bind_address=("localhost",),
                remote_bind_address=("localhost", 1234),
                host_pkey_directories=None,
                logger=hook.log,
            )

    def test_conn_with_extra_parameters(self):
        ssh_hook = SSHHook(ssh_conn_id=self.CONN_SSH_WITH_EXTRA)
        assert ssh_hook.compress is True
        assert ssh_hook.no_host_key_check is True
        assert ssh_hook.allow_host_key_change is False
        assert ssh_hook.look_for_keys is True

    def test_conn_with_extra_parameters_false_look_for_keys(self):
        ssh_hook = SSHHook(ssh_conn_id=self.CONN_SSH_WITH_EXTRA_FALSE_LOOK_FOR_KEYS)
        assert ssh_hook.look_for_keys is False

    @mock.patch("airflow.providers.ssh.hooks.ssh.SSHTunnelForwarder")
    def test_tunnel_with_private_key(self, ssh_mock):
        hook = SSHHook(
            ssh_conn_id=self.CONN_SSH_WITH_PRIVATE_KEY_EXTRA,
            remote_host="remote_host",
            port="port",
            username="username",
            conn_timeout=10,
        )

        with hook.get_tunnel(1234):
            ssh_mock.assert_called_once_with(
                "remote_host",
                ssh_port="port",
                ssh_username="username",
                ssh_pkey=TEST_PKEY,
                ssh_proxy=None,
                local_bind_address=("localhost",),
                remote_bind_address=("localhost", 1234),
                host_pkey_directories=None,
                logger=hook.log,
            )

    @mock.patch("airflow.providers.ssh.hooks.ssh.SSHTunnelForwarder")
    def test_tunnel_with_private_key_passphrase(self, ssh_mock):
        hook = SSHHook(
            ssh_conn_id=self.CONN_SSH_WITH_PRIVATE_KEY_PASSPHRASE_EXTRA,
            remote_host="remote_host",
            port="port",
            username="username",
            conn_timeout=10,
        )

        with hook.get_tunnel(1234):
            ssh_mock.assert_called_once_with(
                "remote_host",
                ssh_port="port",
                ssh_username="username",
                ssh_pkey=TEST_PKEY,
                ssh_proxy=None,
                local_bind_address=("localhost",),
                remote_bind_address=("localhost", 1234),
                host_pkey_directories=None,
                logger=hook.log,
            )

    @mock.patch("airflow.providers.ssh.hooks.ssh.SSHTunnelForwarder")
    def test_tunnel_with_private_key_ecdsa(self, ssh_mock):
        hook = SSHHook(
            ssh_conn_id=self.CONN_SSH_WITH_PRIVATE_KEY_ECDSA_EXTRA,
            remote_host="remote_host",
            port="port",
            username="username",
            conn_timeout=10,
        )

        with hook.get_tunnel(1234):
            ssh_mock.assert_called_once_with(
                "remote_host",
                ssh_port="port",
                ssh_username="username",
                ssh_pkey=TEST_PKEY_ECDSA,
                ssh_proxy=None,
                local_bind_address=("localhost",),
                remote_bind_address=("localhost", 1234),
                host_pkey_directories=None,
                logger=hook.log,
            )

    def test_ssh_connection(self):
        hook = SSHHook(ssh_conn_id="ssh_default")
        with hook.get_conn() as client:
            (_, stdout, _) = client.exec_command("ls")
            assert stdout.read() is not None

    def test_ssh_connection_no_connection_id(self):
        hook = SSHHook(remote_host="localhost")
        assert hook.ssh_conn_id is None
        with hook.get_conn() as client:
            (_, stdout, _) = client.exec_command("ls")
            assert stdout.read() is not None

    def test_ssh_connection_old_cm(self):
        with SSHHook(ssh_conn_id="ssh_default").get_conn() as client:
            (_, stdout, _) = client.exec_command("ls")
            assert stdout.read() is not None

    def test_tunnel(self):
        hook = SSHHook(ssh_conn_id="ssh_default")

        import socket
        import subprocess

        subprocess_kwargs = dict(
            args=["python", "-c", HELLO_SERVER_CMD],
            stdout=subprocess.PIPE,
        )
        with (
            subprocess.Popen(**subprocess_kwargs) as server_handle,
            hook.get_tunnel(local_port=2135, remote_port=2134),
        ):
            server_output = server_handle.stdout.read(5)
            assert server_output == b"ready"
            socket = socket.socket()
            socket.connect(("localhost", 2135))
            response = socket.recv(5)
            assert response == b"hello"
            socket.close()
            server_handle.communicate()
            assert server_handle.returncode == 0

    @mock.patch("airflow.providers.ssh.hooks.ssh.paramiko.SSHClient")
    def test_ssh_connection_with_private_key_extra(self, ssh_mock):
        hook = SSHHook(
            ssh_conn_id=self.CONN_SSH_WITH_PRIVATE_KEY_EXTRA,
            remote_host="remote_host",
            port="port",
            username="username",
            conn_timeout=10,
        )

        with hook.get_conn():
            ssh_mock.return_value.connect.assert_called_once_with(
                banner_timeout=30.0,
                hostname="remote_host",
                username="username",
                pkey=TEST_PKEY,
                timeout=10,
                compress=True,
                port="port",
                sock=None,
                look_for_keys=True,
                auth_timeout=None,
            )

    @mock.patch("airflow.providers.ssh.hooks.ssh.paramiko.SSHClient")
    def test_ssh_connection_with_private_key_passphrase_extra(self, ssh_mock):
        hook = SSHHook(
            ssh_conn_id=self.CONN_SSH_WITH_PRIVATE_KEY_PASSPHRASE_EXTRA,
            remote_host="remote_host",
            port="port",
            username="username",
            conn_timeout=10,
        )

        with hook.get_conn():
            ssh_mock.return_value.connect.assert_called_once_with(
                banner_timeout=30.0,
                hostname="remote_host",
                username="username",
                pkey=TEST_PKEY,
                timeout=10,
                compress=True,
                port="port",
                sock=None,
                look_for_keys=True,
                auth_timeout=None,
            )

    @mock.patch("airflow.providers.ssh.hooks.ssh.paramiko.SSHClient")
    def test_ssh_connection_with_host_key_extra(self, ssh_client):
        hook = SSHHook(ssh_conn_id=self.CONN_SSH_WITH_HOST_KEY_EXTRA)
        assert hook.host_key is not None
        with hook.get_conn():
            assert ssh_client.return_value.connect.called is True
            assert ssh_client.return_value.get_host_keys.return_value.add.called
            assert ssh_client.return_value.get_host_keys.return_value.add.call_args == mock.call(
                hook.remote_host, "ssh-rsa", hook.host_key
            )

    @mock.patch("airflow.providers.ssh.hooks.ssh.paramiko.SSHClient")
    def test_ssh_connection_with_host_key_extra_with_type(self, ssh_client):
        hook = SSHHook(ssh_conn_id=self.CONN_SSH_WITH_HOST_KEY_EXTRA_WITH_TYPE)
        assert hook.host_key is not None
        with hook.get_conn():
            assert ssh_client.return_value.connect.called is True
            assert ssh_client.return_value.get_host_keys.return_value.add.called
            assert ssh_client.return_value.get_host_keys.return_value.add.call_args == mock.call(
                hook.remote_host, "ssh-rsa", hook.host_key
            )

    @mock.patch("airflow.providers.ssh.hooks.ssh.paramiko.SSHClient")
    def test_ssh_connection_with_no_host_key_where_no_host_key_check_is_false(self, ssh_client):
        hook = SSHHook(ssh_conn_id=self.CONN_SSH_WITH_NO_HOST_KEY_AND_NO_HOST_KEY_CHECK_FALSE)
        assert hook.host_key is None
        with hook.get_conn():
            assert ssh_client.return_value.connect.called is True
            assert ssh_client.return_value.get_host_keys.return_value.add.called is False

    def test_ssh_connection_with_host_key_where_no_host_key_check_is_true(self):
        with pytest.raises(ValueError):
            SSHHook(ssh_conn_id=self.CONN_SSH_WITH_HOST_KEY_AND_NO_HOST_KEY_CHECK_TRUE)

    @mock.patch("airflow.providers.ssh.hooks.ssh.paramiko.SSHClient")
    def test_ssh_connection_with_no_host_key_where_no_host_key_check_is_true(self, ssh_client):
        hook = SSHHook(ssh_conn_id=self.CONN_SSH_WITH_NO_HOST_KEY_AND_NO_HOST_KEY_CHECK_TRUE)
        assert hook.host_key is None
        with hook.get_conn():
            assert ssh_client.return_value.connect.called is True
            assert ssh_client.return_value.set_missing_host_key_policy.called is True

    @mock.patch("airflow.providers.ssh.hooks.ssh.paramiko.SSHClient")
    def test_ssh_connection_with_host_key_where_allow_host_key_change_is_true(self, ssh_client):
        hook = SSHHook(ssh_conn_id=self.CONN_SSH_WITH_HOST_KEY_AND_ALLOW_HOST_KEY_CHANGES_TRUE)
        assert hook.host_key is not None
        with hook.get_conn():
            assert ssh_client.return_value.connect.called is True
            assert ssh_client.return_value.load_system_host_keys.called is False
            assert ssh_client.return_value.set_missing_host_key_policy.called is True

    @mock.patch("airflow.providers.ssh.hooks.ssh.paramiko.SSHClient")
    def test_ssh_connection_with_conn_timeout(self, ssh_mock):
        hook = SSHHook(
            remote_host="remote_host",
            port="port",
            username="username",
            password="password",
            conn_timeout=20,
            key_file="fake.file",
            auth_timeout=10,
        )

        with hook.get_conn():
            ssh_mock.return_value.connect.assert_called_once_with(
                banner_timeout=30.0,
                hostname="remote_host",
                username="username",
                password="password",
                key_filename="fake.file",
                timeout=20,
                compress=True,
                port="port",
                sock=None,
                look_for_keys=True,
                auth_timeout=10,
            )

    @pytest.mark.parametrize(
        "cmd_timeout, cmd_timeoutextra, null_cmd_timeoutextra, expected_value",
        [
            (TEST_CMD_TIMEOUT, True, False, TEST_CMD_TIMEOUT),
            (TEST_CMD_TIMEOUT, True, True, TEST_CMD_TIMEOUT),
            (TEST_CMD_TIMEOUT, False, False, TEST_CMD_TIMEOUT),
            (TEST_CMD_TIMEOUT_NOT_SET, True, False, TEST_CMD_TIMEOUT_EXTRA),
            (TEST_CMD_TIMEOUT_NOT_SET, True, True, None),
            (TEST_CMD_TIMEOUT_NOT_SET, False, False, 10),
            (None, True, False, None),
            (None, True, True, None),
            (None, False, False, None),
        ],
    )
    def test_ssh_connection_with_cmd_timeout(
        self, cmd_timeout, cmd_timeoutextra, null_cmd_timeoutextra, expected_value
    ):
        if cmd_timeoutextra:
            if null_cmd_timeoutextra:
                ssh_conn_id = self.CONN_SSH_WITH_NULL_CMD_TIMEOUT_EXTRA
            else:
                ssh_conn_id = self.CONN_SSH_WITH_CMD_TIMEOUT_EXTRA
        else:
            ssh_conn_id = self.CONN_SSH_WITH_NO_EXTRA

        if cmd_timeout == TEST_CMD_TIMEOUT_NOT_SET:
            hook = SSHHook(
                ssh_conn_id=ssh_conn_id,
                remote_host="remote_host",
                port="port",
                username="username",
            )
        else:
            hook = SSHHook(
                ssh_conn_id=ssh_conn_id,
                remote_host="remote_host",
                port="port",
                username="username",
                cmd_timeout=cmd_timeout,
            )
        assert hook.cmd_timeout == expected_value

    @mock.patch("airflow.providers.ssh.hooks.ssh.paramiko.SSHClient")
    def test_ssh_with_extra_disabled_algorithms(self, ssh_mock):
        hook = SSHHook(
            ssh_conn_id=self.CONN_SSH_WITH_EXTRA_DISABLED_ALGORITHMS,
            remote_host="remote_host",
            port="port",
            username="username",
            conn_timeout=42,
        )

        with hook.get_conn():
            ssh_mock.return_value.connect.assert_called_once_with(
                banner_timeout=30.0,
                hostname="remote_host",
                username="username",
                compress=True,
                timeout=42,
                port="port",
                sock=None,
                look_for_keys=True,
                disabled_algorithms=TEST_DISABLED_ALGORITHMS,
                auth_timeout=None,
            )

    @mock.patch("airflow.providers.ssh.hooks.ssh.paramiko.SSHClient")
    def test_ssh_with_extra_ciphers(self, ssh_mock):
        hook = SSHHook(
            ssh_conn_id=self.CONN_SSH_WITH_EXTRA_CIPHERS,
            remote_host="remote_host",
            port="port",
            username="username",
        )

        with hook.get_conn():
            transport = ssh_mock.return_value.get_transport.return_value
            assert transport.get_security_options.return_value.ciphers == TEST_CIPHERS

    def test_openssh_private_key(self):
        # Paramiko behaves differently with OpenSSH generated keys to paramiko
        # generated keys, so we need a test one.
        # This has been generated specifically to put here, it is not otherwise in use
        TEST_OPENSSH_PRIVATE_KEY = "-----BEGIN OPENSSH " + textwrap.dedent(
            """\
        PRIVATE KEY-----
        b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAlwAAAAdzc2gtcn
        NhAAAAAwEAAQAAAIEAuPKIGPWtIpMDrXwMAvNKQlhQ1gXV/tKyufElw/n6hrr6lvtfGhwX
        DihHMsAF+8+KKWQjWgh0fttbIF3+3C56Ns8hgvgMQJT2nyWd7egwqn+LQa08uCEBEka3MO
        arKzj39P66EZ/KQDD29VErlVOd97dPhaR8pOZvzcHxtLbU6rMAAAIA3uBiZd7gYmUAAAAH
        c3NoLXJzYQAAAIEAuPKIGPWtIpMDrXwMAvNKQlhQ1gXV/tKyufElw/n6hrr6lvtfGhwXDi
        hHMsAF+8+KKWQjWgh0fttbIF3+3C56Ns8hgvgMQJT2nyWd7egwqn+LQa08uCEBEka3MOar
        Kzj39P66EZ/KQDD29VErlVOd97dPhaR8pOZvzcHxtLbU6rMAAAADAQABAAAAgA2QC5b4/T
        dZ3J0uSZs1yC5RV6w6RVUokl68Zm6WuF6E+7dyu6iogrBRF9eK6WVr9M/QPh9uG0zqPSaE
        fhobdm7KeycXmtDtrJnXE2ZSk4oU29++TvYZBrAqAli9aHlSArwiLnOIMzY/kIHoSJLJmd
        jwXykdQ7QAd93KPEnkaMzBAAAAQGTyp6/wWqtqpMmYJ5prCGNtpVOGthW5upeiuQUytE/K
        5pyPoq6dUCUxQpkprtkuNAv/ff9nW6yy1v2DWohKfaEAAABBAO3y+erRXmiMreMOAd1S84
        RK2E/LUHOvClQqf6GnVavmIgkxIYEgjcFiWv4xIkTc1/FN6aX5aT4MB3srvuM7sxEAAABB
        AMb6QAkvxo4hT/xKY0E0nG7zCUMXeBV35MEXQK0/InFC7aZ0tjzFsQJzLe/7q7ljIf+9/O
        rCqNhxgOrv7XrRuYMAAAAKYXNoQHNpbm9wZQE=
        -----END OPENSSH PRIVATE KEY-----
        """
        )

        session = settings.Session()
        try:
            conn = Connection(
                conn_id="openssh_pkey",
                host="localhost",
                conn_type="ssh",
                extra={"private_key": TEST_OPENSSH_PRIVATE_KEY},
            )
            session.add(conn)
            session.flush()
            hook = SSHHook(ssh_conn_id=conn.conn_id)
            assert isinstance(hook.pkey, paramiko.RSAKey)
        finally:
            session.delete(conn)
            session.commit()

    def test_oneline_key(self):
        TEST_ONELINE_KEY = "-----BEGIN OPENSSHPRIVATE KEY-----asdfg-----END OPENSSHPRIVATE KEY-----"
        session = settings.Session()
        conn = Connection(
            conn_id="openssh_pkey",
            host="localhost",
            conn_type="ssh",
            extra={"private_key": TEST_ONELINE_KEY},
        )
        session.add(conn)
        session.flush()
        with pytest.raises(AirflowException, match="Key must have BEGIN and END"):
            SSHHook(ssh_conn_id=conn.conn_id)
        session.delete(conn)
        session.commit()

    @pytest.mark.flaky(reruns=5)
    def test_exec_ssh_client_command(self):
        hook = SSHHook(
            ssh_conn_id="ssh_default",
            conn_timeout=30,
            banner_timeout=100,
        )
        with hook.get_conn() as client:
            ret = hook.exec_ssh_client_command(
                client,
                "echo airflow",
                False,
                None,
                30,
            )
            assert ret == (0, b"airflow\n", b"")

    def test_command_timeout_success(self):
        hook = SSHHook(
            ssh_conn_id="ssh_default",
            conn_timeout=30,
            cmd_timeout=2,
            banner_timeout=100,
        )

        with hook.get_conn() as client:
            ret = hook.exec_ssh_client_command(
                client,
                "sleep 0.1; echo airflow",
                False,
                None,
            )
            assert ret == (0, b"airflow\n", b"")

    def test_command_timeout_fail(self):
        hook = SSHHook(
            ssh_conn_id="ssh_default",
            conn_timeout=30,
            cmd_timeout=0.001,
            banner_timeout=100,
        )

        with hook.get_conn() as client:
            with pytest.raises(AirflowException):
                hook.exec_ssh_client_command(
                    client,
                    "sleep 1",
                    False,
                    None,
                )

    def test_command_timeout_not_set(self, monkeypatch):
        hook = SSHHook(
            ssh_conn_id="ssh_default",
            conn_timeout=30,
            cmd_timeout=None,
            banner_timeout=100,
        )

        # Mock the timeout to not wait for that many seconds
        monkeypatch.setattr("airflow.providers.ssh.hooks.ssh.CMD_TIMEOUT", 0.001)

        with hook.get_conn() as client:
            # sleeping for more secs than default timeout
            # to validate that no timeout is applied
            hook.exec_ssh_client_command(
                client,
                "sleep 0.1",
                environment=False,
                get_pty=None,
            )

    @mock.patch("airflow.providers.ssh.hooks.ssh.paramiko.SSHClient")
    def test_ssh_connection_with_no_host_key_check_true_and_allow_host_key_changes_true(self, ssh_mock):
        hook = SSHHook(ssh_conn_id=self.CONN_SSH_WITH_NO_HOST_KEY_CHECK_TRUE_AND_ALLOW_HOST_KEY_CHANGES_TRUE)
        with hook.get_conn():
            assert ssh_mock.return_value.set_missing_host_key_policy.called is True
            assert isinstance(
                ssh_mock.return_value.set_missing_host_key_policy.call_args.args[0], paramiko.AutoAddPolicy
            )
            assert ssh_mock.return_value.load_host_keys.called is False

    @mock.patch("airflow.providers.ssh.hooks.ssh.paramiko.SSHClient")
    def test_ssh_connection_with_no_host_key_check_true_and_allow_host_key_changes_false(self, ssh_mock):
        hook = SSHHook(ssh_conn_id=self.CONN_SSH_WITH_NO_HOST_KEY_CHECK_TRUE_AND_ALLOW_HOST_KEY_CHANGES_FALSE)

        with mock.patch("os.path.isfile", return_value=True):
            with hook.get_conn():
                assert ssh_mock.return_value.set_missing_host_key_policy.called is True
                assert isinstance(
                    ssh_mock.return_value.set_missing_host_key_policy.call_args.args[0],
                    paramiko.AutoAddPolicy,
                )
                assert ssh_mock.return_value.load_host_keys.called is True

        ssh_mock.reset_mock()
        with mock.patch("os.path.isfile", return_value=False):
            # Reset ssh hook to initial state
            hook = SSHHook(
                ssh_conn_id=self.CONN_SSH_WITH_NO_HOST_KEY_CHECK_TRUE_AND_ALLOW_HOST_KEY_CHANGES_FALSE
            )
            with hook.get_conn():
                assert ssh_mock.return_value.set_missing_host_key_policy.called is True
                assert isinstance(
                    ssh_mock.return_value.set_missing_host_key_policy.call_args.args[0],
                    paramiko.AutoAddPolicy,
                )
                assert ssh_mock.return_value.load_host_keys.called is False

    def test_connection_success(self):
        hook = SSHHook(ssh_conn_id="ssh_default")
        status, msg = hook.test_connection()
        assert status is True
        assert msg == "Connection successfully tested"

    def test_connection_failure(self):
        hook = SSHHook(ssh_conn_id="ssh_default")
        hook.get_conn = mock.MagicMock(name="mock_conn", side_effect=Exception("Test failure case"))
        status, msg = hook.test_connection()
        assert status is False
        assert msg == "Test failure case"

    def test_ssh_connection_client_is_reused_if_open(self):
        hook = SSHHook(ssh_conn_id="ssh_default")
        client1 = hook.get_conn()
        client2 = hook.get_conn()
        assert client1 is client2
        assert client2.get_transport().is_active()

    def test_ssh_connection_client_is_recreated_if_closed(self):
        hook = SSHHook(ssh_conn_id="ssh_default")
        client1 = hook.get_conn()
        client1.close()
        client2 = hook.get_conn()
        assert client1 is not client2
        assert client2.get_transport().is_active()

    def test_ssh_connection_client_is_recreated_if_transport_closed(self):
        hook = SSHHook(ssh_conn_id="ssh_default")
        client1 = hook.get_conn()
        client1.get_transport().close()
        client2 = hook.get_conn()
        assert client1 is not client2
        assert client2.get_transport().is_active()

    @mock.patch("paramiko.SSHClient")
    @mock.patch("paramiko.ProxyCommand")
    def test_ssh_hook_with_proxy_command(self, mock_proxy_command, mock_ssh_client):
        # Mock transport and proxy command behavior
        mock_transport = mock.MagicMock()
        mock_ssh_client.return_value.get_transport.return_value = mock_transport
        mock_proxy_command.return_value = mock.MagicMock()

        # Create the SSHHook with the proxy command
        host_proxy_cmd = "ncat --proxy-auth proxy_user:**** --proxy proxy_host:port %h %p"
        hook = SSHHook(
            remote_host="example.com",
            username="user",
            host_proxy_cmd=host_proxy_cmd,
        )
        hook.get_conn()

        mock_proxy_command.assert_called_once_with(host_proxy_cmd)
        mock_ssh_client.return_value.connect.assert_called_once_with(
            hostname="example.com",
            username="user",
            timeout=None,
            compress=True,
            port=22,
            sock=mock_proxy_command.return_value,
            look_for_keys=True,
            banner_timeout=30.0,
            auth_timeout=None,
        )
