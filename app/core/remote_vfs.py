"""
Remote Virtual Filesystem (SFTP, Amazon S3 / Compatible, FTP, FTPS)
Enables seamless browsing, comparison, and file reading across remote targets via URIs:
  sftp://<profile>/<path>
  s3://<profile>/<prefix>
  ftp://<profile>/<path>
  ftps://<profile>/<path>

Secrets are resolved at runtime via SSH key paths, environment variables (`password_env`),
AWS CLI profiles, or in-memory session secrets (never stored plaintext on disk).
"""

import ftplib
import io
import os
import posixpath
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.session_manager import SessionManager

try:
    import paramiko
    HAS_PARAMIKO = True
except ImportError:
    HAS_PARAMIKO = False

try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


@dataclass
class RemoteEntry:
    """Represents a file or directory entry returned by a remote adapter."""
    path: str
    is_dir: bool
    size: int = 0
    mtime: float = 0.0


def _join_remote_rel(base_path: str, rel_path: str) -> str:
    b = (base_path or "").strip("/")
    r = (rel_path or "").strip("/")
    if b and r:
        return f"{b}/{r}"
    return b or r


class BaseRemoteAdapter:
    """Protocol adapter interface for remote filesystem backends."""

    def list_entries(self, profile: Dict[str, Any], sub_path: str, secret: Optional[str] = None) -> List[RemoteEntry]:
        raise NotImplementedError

    def read_file_bytes(self, profile: Dict[str, Any], sub_path: str, secret: Optional[str] = None) -> bytes:
        raise NotImplementedError

    def write_file_bytes(self, profile: Dict[str, Any], sub_path: str, data: bytes, secret: Optional[str] = None) -> None:
        raise NotImplementedError

    def test_connection(self, profile: Dict[str, Any], secret: Optional[str] = None) -> Tuple[bool, str]:
        raise NotImplementedError


class SFTPAdapter(BaseRemoteAdapter):
    """SSH/SFTP backend powered by Paramiko."""

    def _connect(self, profile: Dict[str, Any], secret: Optional[str]):
        if not HAS_PARAMIKO:
            raise ImportError("Paramiko is not installed. Install with `pip install paramiko`.")
        host = profile.get("host", "").strip()
        port = int(profile.get("port") or 22)
        username = profile.get("username", "").strip() or os.environ.get("USERNAME", "")
        key_path = (profile.get("key_path") or "").strip()
        env_var = (profile.get("password_env") or "").strip()
        password = secret if secret else (os.environ.get(env_var) if env_var else None)

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        kwargs: Dict[str, Any] = {
            "hostname": host,
            "port": port,
            "username": username,
            "timeout": 12,
        }
        if key_path and os.path.isfile(key_path):
            kwargs["key_filename"] = key_path
        if password:
            kwargs["password"] = password
        client.connect(**kwargs)
        sftp = client.open_sftp()
        return client, sftp

    def list_entries(self, profile: Dict[str, Any], sub_path: str, secret: Optional[str] = None) -> List[RemoteEntry]:
        root_rel = _join_remote_rel(profile.get("base_path", ""), sub_path)
        remote_root = "/" + root_rel if root_rel else "/"
        client, sftp = self._connect(profile, secret)
        entries: List[RemoteEntry] = []
        try:
            def _walk(cur_remote: str, rel_prefix: str):
                for attr in sftp.listdir_attr(cur_remote):
                    name = attr.filename
                    if name in (".", ".."):
                        continue
                    rel_p = f"{rel_prefix}/{name}".lstrip("/")
                    full_r = posixpath.join(cur_remote, name)
                    is_dir = stat.S_ISDIR(attr.st_mode or 0)
                    entries.append(RemoteEntry(
                        path=rel_p,
                        is_dir=is_dir,
                        size=0 if is_dir else int(attr.st_size or 0),
                        mtime=float(attr.st_mtime or 0.0),
                    ))
                    if is_dir:
                        _walk(full_r, rel_p)

            _walk(remote_root, "")
        finally:
            sftp.close()
            client.close()
        return entries

    def read_file_bytes(self, profile: Dict[str, Any], sub_path: str, secret: Optional[str] = None) -> bytes:
        full_rel = _join_remote_rel(profile.get("base_path", ""), sub_path)
        client, sftp = self._connect(profile, secret)
        try:
            with sftp.open("/" + full_rel, "rb") as f:
                return f.read()
        finally:
            sftp.close()
            client.close()

    def write_file_bytes(self, profile: Dict[str, Any], sub_path: str, data: bytes, secret: Optional[str] = None) -> None:
        full_rel = _join_remote_rel(profile.get("base_path", ""), sub_path)
        client, sftp = self._connect(profile, secret)
        try:
            with sftp.open("/" + full_rel, "wb") as f:
                f.write(data)
        finally:
            sftp.close()
            client.close()

    def test_connection(self, profile: Dict[str, Any], secret: Optional[str] = None) -> Tuple[bool, str]:
        try:
            client, sftp = self._connect(profile, secret)
            root_rel = "/" + _join_remote_rel(profile.get("base_path", ""), "")
            items = sftp.listdir(root_rel)
            sftp.close()
            client.close()
            return True, f"Connected via SFTP ({len(items)} top-level items in {root_rel})"
        except Exception as e:
            return False, f"SFTP error: {e}"


class S3Adapter(BaseRemoteAdapter):
    """Amazon S3 / S3-compatible object storage backend powered by boto3."""

    def _client(self, profile: Dict[str, Any], secret: Optional[str]):
        if not HAS_BOTO3:
            raise ImportError("boto3 is not installed. Install with `pip install boto3`.")
        aws_profile = (profile.get("aws_profile") or "").strip()
        session = boto3.Session(profile_name=aws_profile) if aws_profile else boto3.Session()
        kwargs: Dict[str, Any] = {}
        if profile.get("endpoint_url"):
            kwargs["endpoint_url"] = profile["endpoint_url"].strip()
        if profile.get("region"):
            kwargs["region_name"] = profile["region"].strip()
        if profile.get("username"):
            kwargs["aws_access_key_id"] = profile["username"].strip()
        env_var = (profile.get("password_env") or "").strip()
        secret_key = secret if secret else (os.environ.get(env_var) if env_var else None)
        if secret_key:
            kwargs["aws_secret_access_key"] = secret_key
        return session.client("s3", **kwargs)

    def list_entries(self, profile: Dict[str, Any], sub_path: str, secret: Optional[str] = None) -> List[RemoteEntry]:
        bucket = (profile.get("bucket") or profile.get("host") or "").strip()
        if not bucket:
            raise ValueError("S3 profile requires a Bucket name.")
        prefix = _join_remote_rel(profile.get("base_path", ""), sub_path)
        if prefix and not prefix.endswith("/"):
            prefix += "/"

        client = self._client(profile, secret)
        paginator = client.get_paginator("list_objects_v2")
        entries: List[RemoteEntry] = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                rel = key[len(prefix):] if prefix and key.startswith(prefix) else key
                rel = rel.strip("/")
                if not rel:
                    continue
                is_dir = key.endswith("/")
                mtime = obj["LastModified"].timestamp() if obj.get("LastModified") else 0.0
                entries.append(RemoteEntry(
                    path=rel,
                    is_dir=is_dir,
                    size=0 if is_dir else int(obj.get("Size", 0)),
                    mtime=float(mtime),
                ))
        return entries

    def read_file_bytes(self, profile: Dict[str, Any], sub_path: str, secret: Optional[str] = None) -> bytes:
        bucket = (profile.get("bucket") or profile.get("host") or "").strip()
        key = _join_remote_rel(profile.get("base_path", ""), sub_path)
        client = self._client(profile, secret)
        resp = client.get_object(Bucket=bucket, Key=key)
        return resp["Body"].read()

    def write_file_bytes(self, profile: Dict[str, Any], sub_path: str, data: bytes, secret: Optional[str] = None) -> None:
        bucket = (profile.get("bucket") or profile.get("host") or "").strip()
        key = _join_remote_rel(profile.get("base_path", ""), sub_path)
        client = self._client(profile, secret)
        client.put_object(Bucket=bucket, Key=key, Body=data)

    def test_connection(self, profile: Dict[str, Any], secret: Optional[str] = None) -> Tuple[bool, str]:
        try:
            bucket = (profile.get("bucket") or profile.get("host") or "").strip()
            prefix = _join_remote_rel(profile.get("base_path", ""), "")
            client = self._client(profile, secret)
            resp = client.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=20)
            count = len(resp.get("Contents", []))
            return True, f"Connected to S3 bucket '{bucket}' ({count} sample key(s) listed)"
        except Exception as e:
            return False, f"S3 error: {e}"


class FTPAdapter(BaseRemoteAdapter):
    """FTP / FTPS backend powered by Python stdlib ftplib."""

    def __init__(self, use_tls: bool = False):
        self.use_tls = use_tls

    def _connect(self, profile: Dict[str, Any], secret: Optional[str]):
        host = profile.get("host", "").strip()
        port = int(profile.get("port") or (990 if self.use_tls else 21))
        user = profile.get("username", "").strip() or "anonymous"
        env_var = (profile.get("password_env") or "").strip()
        passwd = secret if secret else (os.environ.get(env_var, "") if env_var else "")
        ftp = ftplib.FTP_TLS() if self.use_tls else ftplib.FTP()
        ftp.connect(host, port, timeout=12)
        ftp.login(user, passwd)
        if self.use_tls and isinstance(ftp, ftplib.FTP_TLS):
            ftp.prot_p()
        return ftp

    def list_entries(self, profile: Dict[str, Any], sub_path: str, secret: Optional[str] = None) -> List[RemoteEntry]:
        root_rel = "/" + _join_remote_rel(profile.get("base_path", ""), sub_path)
        ftp = self._connect(profile, secret)
        entries: List[RemoteEntry] = []
        try:
            def _walk(cur_dir: str, prefix: str):
                try:
                    for name, facts in ftp.mlsd(cur_dir):
                        if name in (".", ".."):
                            continue
                        ftype = facts.get("type", "").lower()
                        is_dir = ftype in ("dir", "cdir", "pdir")
                        rel_p = f"{prefix}/{name}".lstrip("/")
                        size = 0 if is_dir else int(facts.get("size", 0) or 0)
                        mod = facts.get("modify", "")
                        mtime = 0.0
                        if len(mod) >= 14:
                            try:
                                mtime = datetime.strptime(mod[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).timestamp()
                            except ValueError:
                                mtime = 0.0
                        entries.append(RemoteEntry(path=rel_p, is_dir=is_dir, size=size, mtime=mtime))
                        if is_dir:
                            _walk(posixpath.join(cur_dir, name), rel_p)
                except ftplib.error_perm:
                    for name in ftp.nlst(cur_dir):
                        base = posixpath.basename(name.rstrip("/"))
                        if base in ("", ".", ".."):
                            continue
                        entries.append(RemoteEntry(path=f"{prefix}/{base}".lstrip("/"), is_dir=False, size=0, mtime=0.0))

            _walk(root_rel, "")
        finally:
            try:
                ftp.quit()
            except Exception:
                ftp.close()
        return entries

    def read_file_bytes(self, profile: Dict[str, Any], sub_path: str, secret: Optional[str] = None) -> bytes:
        remote_file = "/" + _join_remote_rel(profile.get("base_path", ""), sub_path)
        buf = io.BytesIO()
        ftp = self._connect(profile, secret)
        try:
            ftp.retrbinary(f"RETR {remote_file}", buf.write)
            return buf.getvalue()
        finally:
            try:
                ftp.quit()
            except Exception:
                ftp.close()

    def write_file_bytes(self, profile: Dict[str, Any], sub_path: str, data: bytes, secret: Optional[str] = None) -> None:
        remote_file = "/" + _join_remote_rel(profile.get("base_path", ""), sub_path)
        ftp = self._connect(profile, secret)
        try:
            ftp.storbinary(f"STOR {remote_file}", io.BytesIO(data))
        finally:
            try:
                ftp.quit()
            except Exception:
                ftp.close()

    def test_connection(self, profile: Dict[str, Any], secret: Optional[str] = None) -> Tuple[bool, str]:
        try:
            ftp = self._connect(profile, secret)
            pwd = ftp.pwd()
            ftp.quit()
            return True, f"Connected via {'FTPS' if self.use_tls else 'FTP'} (PWD: {pwd})"
        except Exception as e:
            return False, f"FTP error: {e}"


class RemoteVFS:
    """URI dispatcher and adapter registry for SFTP, S3, FTP, and FTPS virtual filesystems."""

    SUPPORTED_SCHEMES = ("sftp", "s3", "ftp", "ftps")
    _session_secrets: Dict[str, str] = {}
    _adapters: Dict[str, BaseRemoteAdapter] = {
        "sftp": SFTPAdapter(),
        "s3": S3Adapter(),
        "ftp": FTPAdapter(use_tls=False),
        "ftps": FTPAdapter(use_tls=True),
    }

    @classmethod
    def register_adapter(cls, scheme: str, adapter: BaseRemoteAdapter) -> None:
        """Registers a custom or mock adapter for a protocol scheme."""
        cls._adapters[scheme.lower()] = adapter

    @classmethod
    def reset_default_adapters(cls) -> None:
        cls._adapters = {
            "sftp": SFTPAdapter(),
            "s3": S3Adapter(),
            "ftp": FTPAdapter(use_tls=False),
            "ftps": FTPAdapter(use_tls=True),
        }

    @classmethod
    def set_session_secret(cls, profile_name: str, secret: str) -> None:
        if secret:
            cls._session_secrets[profile_name] = secret
        else:
            cls._session_secrets.pop(profile_name, None)

    @classmethod
    def get_session_secret(cls, profile_name: str) -> Optional[str]:
        return cls._session_secrets.get(profile_name)

    @staticmethod
    def is_remote_path(path: str) -> bool:
        if not path or "://" not in path:
            return False
        scheme = path.split("://", 1)[0].lower()
        return scheme in RemoteVFS.SUPPORTED_SCHEMES

    @staticmethod
    def parse_remote_uri(uri: str) -> Tuple[str, str, str]:
        """Splits `scheme://profile/sub/path` into `(scheme, profile_name, inner_path)`."""
        if not RemoteVFS.is_remote_path(uri):
            raise ValueError(f"Unsupported remote URI: {uri}")
        scheme, rest = uri.split("://", 1)
        rest = rest.lstrip("/")
        if "/" in rest:
            profile_name, inner_path = rest.split("/", 1)
        else:
            profile_name, inner_path = rest, ""
        return scheme.lower(), profile_name, inner_path.replace("\\", "/").strip("/")

    @staticmethod
    def build_remote_uri(scheme: str, profile_name: str, inner_path: str = "") -> str:
        clean_inner = (inner_path or "").replace("\\", "/").strip("/")
        base = f"{scheme.lower()}://{profile_name}"
        return f"{base}/{clean_inner}" if clean_inner else base

    @classmethod
    def _resolve(cls, uri: str) -> Tuple[BaseRemoteAdapter, Dict[str, Any], str, Optional[str]]:
        scheme, profile_name, sub_path = cls.parse_remote_uri(uri)
        profiles = SessionManager.get_remote_profiles()
        profile = profiles.get(profile_name)
        if not profile:
            raise KeyError(f"Remote profile '{profile_name}' not found.")
        adapter = cls._adapters.get(scheme)
        if not adapter:
            raise ValueError(f"No adapter registered for scheme '{scheme}'")
        secret = cls.get_session_secret(profile_name)
        return adapter, profile, sub_path, secret

    @classmethod
    def list_entries(cls, uri: str) -> List[RemoteEntry]:
        adapter, profile, sub_path, secret = cls._resolve(uri)
        return adapter.list_entries(profile, sub_path, secret=secret)

    @classmethod
    def read_file_bytes(cls, uri: str) -> bytes:
        adapter, profile, sub_path, secret = cls._resolve(uri)
        return adapter.read_file_bytes(profile, sub_path, secret=secret)

    @classmethod
    def write_file_bytes(cls, uri: str, data: bytes) -> None:
        adapter, profile, sub_path, secret = cls._resolve(uri)
        adapter.write_file_bytes(profile, sub_path, data, secret=secret)

    @classmethod
    def test_connection(cls, profile_cfg: Dict[str, Any], session_secret: Optional[str] = None) -> Tuple[bool, str]:
        scheme = (profile_cfg.get("protocol") or "sftp").lower()
        adapter = cls._adapters.get(scheme)
        if not adapter:
            return False, f"Unsupported protocol: {scheme}"
        return adapter.test_connection(profile_cfg, secret=session_secret)
