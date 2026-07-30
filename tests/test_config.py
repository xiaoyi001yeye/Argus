import tempfile
import unittest
from pathlib import Path

from argus.config import ConfigError, load_config


class ConfigTest(unittest.TestCase):
    def test_loads_password_ssh_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config" / "environments.yaml"
            config_path.parent.mkdir()
            config_path.write_text(
                """
environments:
  production:
    provider: ssh
    ssh:
      host: 172.17.162.104
      port: 2222
      username: root
      password: secret
      connect_timeout: 7
      known_hosts: ~/.ssh/known_hosts
    log_sources:
      appserver:
        path: /var/log/app/app.log
        description: App log
""",
                encoding="utf-8",
            )

            environment = load_config(config_path).environments["production"]

        self.assertIsNotNone(environment.ssh)
        if environment.ssh is None:
            self.fail("SSH config was not loaded")
        self.assertEqual(environment.ssh.host, "172.17.162.104")
        self.assertEqual(environment.ssh.port, 2222)
        self.assertEqual(environment.ssh.username, "root")
        self.assertEqual(environment.ssh.password, "secret")
        self.assertEqual(environment.ssh.connect_timeout, 7)
        self.assertEqual(environment.ssh.known_hosts, Path("~/.ssh/known_hosts").expanduser())

    def test_rejects_multiple_ssh_authentication_methods(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config" / "environments.yaml"
            config_path.parent.mkdir()
            config_path.write_text(
                """
environments:
  production:
    provider: ssh
    ssh:
      host: 172.17.162.104
      username: root
      password: secret
      private_key: ~/.ssh/id_ed25519
    log_sources:
      appserver:
        path: /var/log/app/app.log
""",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ConfigError, "only one SSH authentication"):
                load_config(config_path)


if __name__ == "__main__":
    unittest.main()
