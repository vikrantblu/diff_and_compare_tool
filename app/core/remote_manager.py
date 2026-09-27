import os
import paramiko

class RemoteManager:
    def __init__(self):
        self.connections = {}

    def connect_sftp(self, name, host, port, username, password=None, key_filepath=None):
        try:
            transport = paramiko.Transport((host, port))
            if key_filepath:
                key = paramiko.RSAKey.from_private_key_file(key_filepath)
                transport.connect(username=username, pkey=key)
            else:
                transport.connect(username=username, password=password)
            sftp = paramiko.SFTPClient.from_transport(transport)
            self.connections[name] = {'type': 'sftp', 'client': sftp, 'transport': transport}
            return True, "Connected successfully"
        except Exception as e:
            return False, str(e)

    def connect_mock_s3(self, name, bucket, access_key, secret_key):
        self.connections[name] = {'type': 's3', 'bucket': bucket}
        return True, "Mock S3 Connected"

    def connect_mock_onedrive(self, name, token):
        self.connections[name] = {'type': 'onedrive'}
        return True, "Mock OneDrive Connected"

    def disconnect(self, name):
        if name in self.connections:
            conn = self.connections[name]
            if conn['type'] == 'sftp':
                conn['client'].close()
                conn['transport'].close()
            del self.connections[name]

    def download_file(self, name, remote_path, local_path):
        conn = self.connections.get(name)
        if not conn:
            raise ValueError(f"Connection {name} not found")
        
        if conn['type'] == 'sftp':
            conn['client'].get(remote_path, local_path)
        elif conn['type'] in ['s3', 'onedrive']:
            # Mock download
            with open(local_path, 'w', encoding='utf-8') as f:
                f.write(f"Mock content downloaded from {conn['type']} at {remote_path}\n")

    def upload_file(self, name, local_path, remote_path):
        conn = self.connections.get(name)
        if not conn:
            raise ValueError(f"Connection {name} not found")

        if conn['type'] == 'sftp':
            conn['client'].put(local_path, remote_path)
        elif conn['type'] in ['s3', 'onedrive']:
            # Mock upload
            print(f"Mock uploaded {local_path} to {conn['type']} at {remote_path}")

    def list_dir(self, name, remote_path):
        conn = self.connections.get(name)
        if not conn:
            raise ValueError(f"Connection {name} not found")

        if conn['type'] == 'sftp':
            return conn['client'].listdir(remote_path)
        elif conn['type'] in ['s3', 'onedrive']:
            return ["mock_file1.txt", "mock_file2.txt", "mock_folder/"]
