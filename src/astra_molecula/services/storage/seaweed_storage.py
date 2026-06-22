"""
SeaweedFS 存储实现
支持 Filer API（主要）和 S3 API（备用）
"""
import logging
import aiohttp
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, AsyncIterator, Optional

from astra_molecula.core.config import storage as storage_config

logger = logging.getLogger("seaweed_storage")


class SeaweedStorage:
    """SeaweedFS Filer API 存储实现"""
    
    def __init__(self):
        self.filer_endpoint = storage_config.filer_endpoint
        self.bucket = storage_config.bucket
        self.base_url = storage_config.get_filer_base_url()
        
        logger.info("SeaweedStorage initialized: filer=%s, bucket=%s",
                   self.filer_endpoint, self.bucket)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """复用单个 ClientSession。

        原实现每个调用 new 一个 ClientSession → 每次都重新做集群 DNS 解析;在 ndots/
        search 域异常时单次解析可达 ~8s,导致每个存储操作都慢、列表型接口 N 次放大到超时。
        这里复用带 DNS 缓存的 connector(只解析一次),并设置超时使连接失败快速返回,
        而非 aiohttp 默认的 300s 挂死。
        """
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                use_dns_cache=True, ttl_dns_cache=300, limit=50, limit_per_host=20,
            )
            timeout = aiohttp.ClientTimeout(total=120, connect=10, sock_connect=10, sock_read=60)
            self._session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        return self._session

    @asynccontextmanager
    async def _session_cm(self):
        """提供共享 session 的异步上下文管理器(用于替换原先逐次 new 的 ClientSession);
        退出时不关闭,供后续调用复用。"""
        session = await self._get_session()
        yield session

    async def aclose(self) -> None:
        """关闭共享 session(进程退出/重置时调用,可选)。"""
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    def _get_url(self, remote_key: str) -> str:
        """构建完整的 Filer URL"""
        # 确保 remote_key 不以 / 开头
        key = remote_key.lstrip('/')
        return f"{self.base_url}/{key}"
    
    async def upload_file(self, local_path: Path, remote_key: str) -> str:
        """
        上传本地文件到 SeaweedFS
        
        Args:
            local_path: 本地文件路径
            remote_key: 远程存储路径（不含 bucket）
            
        Returns:
            存储的 remote_key
        """
        url = self._get_url(remote_key)
        
        async with self._session_cm() as session:
            with open(local_path, 'rb') as f:
                data = aiohttp.FormData()
                data.add_field('file', f, filename=local_path.name)
                async with session.post(url, data=data) as response:
                    if response.status not in (200, 201):
                        text = await response.text()
                        raise Exception(f"Upload failed: {response.status} - {text}")
        
        logger.info("Uploaded file: %s -> %s", local_path, remote_key)
        return remote_key
    
    async def upload_bytes(self, data: bytes, remote_key: str, content_type: str = None) -> str:
        """
        上传字节数据到 SeaweedFS
        
        Args:
            data: 要上传的字节数据
            remote_key: 远程存储路径
            content_type: MIME 类型（可选）
            
        Returns:
            存储的 remote_key
        """
        url = self._get_url(remote_key)
        headers = {}
        if content_type:
            headers['Content-Type'] = content_type
        
        async with self._session_cm() as session:
            # 使用 multipart form 上传
            form_data = aiohttp.FormData()
            form_data.add_field('file', data, 
                               filename=remote_key.split('/')[-1],
                               content_type=content_type or 'application/octet-stream')
            async with session.post(url, data=form_data) as response:
                if response.status not in (200, 201):
                    text = await response.text()
                    raise Exception(f"Upload failed: {response.status} - {text}")
        
        logger.info("Uploaded bytes: %d bytes -> %s", len(data), remote_key)
        return remote_key
    
    async def download_file(self, remote_key: str, local_path: Path) -> Path:
        """
        从 SeaweedFS 下载文件到本地
        
        Args:
            remote_key: 远程存储路径
            local_path: 本地保存路径
            
        Returns:
            本地文件路径
        """
        url = self._get_url(remote_key)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with self._session_cm() as session:
            async with session.get(url) as response:
                if response.status == 404:
                    raise FileNotFoundError(f"File not found: {remote_key}")
                if response.status != 200:
                    text = await response.text()
                    raise Exception(f"Download failed: {response.status} - {text}")
                
                with open(local_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        f.write(chunk)
        
        logger.info("Downloaded file: %s -> %s", remote_key, local_path)
        return local_path
    
    async def download_bytes(self, remote_key: str) -> bytes:
        """
        从 SeaweedFS 下载文件内容为字节
        
        Args:
            remote_key: 远程存储路径
            
        Returns:
            文件内容的字节数据
        """
        url = self._get_url(remote_key)
        
        async with self._session_cm() as session:
            async with session.get(url) as response:
                if response.status == 404:
                    raise FileNotFoundError(f"File not found: {remote_key}")
                if response.status != 200:
                    text = await response.text()
                    raise Exception(f"Download failed: {response.status} - {text}")
                
                data = await response.read()
        
        logger.debug("Downloaded bytes: %s (%d bytes)", remote_key, len(data))
        return data
    
    async def get_presigned_url(self, remote_key: str, expires: int = None) -> str:
        """
        生成直接下载 URL（Filer 不需要签名，直接返回 URL）
        
        Args:
            remote_key: 远程存储路径
            expires: URL 过期时间（秒），Filer API 不支持，忽略
            
        Returns:
            下载 URL
        """
        url = self._get_url(remote_key)
        logger.debug("Generated download URL for %s", remote_key)
        return url
    
    async def delete_file(self, remote_key: str) -> bool:
        """
        删除 SeaweedFS 中的文件
        
        Args:
            remote_key: 远程存储路径
            
        Returns:
            是否删除成功
        """
        url = self._get_url(remote_key)
        
        async with self._session_cm() as session:
            async with session.delete(url) as response:
                if response.status not in (200, 202, 204, 404):
                    text = await response.text()
                    raise Exception(f"Delete failed: {response.status} - {text}")
        
        logger.info("Deleted file: %s", remote_key)
        return True
    
    async def delete_files(self, remote_keys: List[str]) -> bool:
        """
        批量删除 SeaweedFS 中的文件
        
        Args:
            remote_keys: 远程存储路径列表
            
        Returns:
            是否删除成功
        """
        for key in remote_keys:
            await self.delete_file(key)
        
        logger.info("Deleted %d files", len(remote_keys))
        return True
    
    async def list_files(self, prefix: str) -> List[str]:
        """
        列出指定前缀的文件
        
        Args:
            prefix: 路径前缀
            
        Returns:
            文件路径列表
        """
        url = self._get_url(prefix.rstrip('/') + '/')
        params = {'pretty': 'y'}
        
        result = []
        async with self._session_cm() as session:
            async with session.get(url, params=params, headers={'Accept': 'application/json'}) as response:
                if response.status == 404:
                    return []
                if response.status != 200:
                    return []
                
                try:
                    data = await response.json()
                    entries = data.get('Entries', []) or []
                    for entry in entries:
                        name = entry.get('FullPath', '') or entry.get('Name', '')
                        if name:
                            # 提取相对路径
                            if name.startswith('/buckets/' + self.bucket + '/'):
                                name = name[len('/buckets/' + self.bucket + '/'):]
                            result.append(name)
                except Exception:
                    pass
        
        logger.debug("Listed %d files with prefix: %s", len(result), prefix)
        return result

    async def list_files_recursive(self, prefix: str) -> List[str]:
        """
        递归列出指定前缀下的所有文件（包括子目录中的文件）
        
        Args:
            prefix: 路径前缀
            
        Returns:
            所有文件路径列表（不包括目录本身）
        """
        all_files = []
        url = self._get_url(prefix.rstrip('/') + '/')
        params = {'pretty': 'y'}

        async with self._session_cm() as session:
            async with session.get(url, params=params, headers={'Accept': 'application/json'}) as response:
                if response.status != 200:
                    return []

                try:
                    data = await response.json()
                    entries = data.get('Entries', []) or []
                    for entry in entries:
                        full_path = entry.get('FullPath', '') or entry.get('Name', '')
                        if not full_path:
                            continue

                        # 提取相对路径
                        name = full_path
                        if name.startswith('/buckets/' + self.bucket + '/'):
                            name = name[len('/buckets/' + self.bucket + '/'):]

                        # 判断是否为目录：SeaweedFS JSON 返回小写 "chunks"
                        chunks = entry.get('chunks')
                        has_chunks = chunks is not None and isinstance(chunks, list) and len(chunks) > 0
                        mode = entry.get('Mode', 0)
                        # SeaweedFS 目录使用特殊 mode 位 (0o20000000000 或标准 0o40000)
                        is_dir_mode = (mode & 0o20000000000) != 0 or (mode & 0o40000) != 0
                        # 目录：无 chunks 且 mode 表示为目录；或 FullPath 以 / 结尾
                        is_dir = (not has_chunks and is_dir_mode) or name.endswith('/')

                        if is_dir:
                            # 递归列出子目录
                            sub_files = await self.list_files_recursive(name)
                            all_files.extend(sub_files)
                        else:
                            all_files.append(name)
                except Exception as e:
                    logger.warning("Error listing files recursively at %s: %s", prefix, e)

        logger.debug("Listed %d files recursively with prefix: %s", len(all_files), prefix)
        return all_files

    async def list_entries_recursive(self, prefix: str) -> List[dict]:
        """递归列出文件及其大小：返回 [{'path': str, 'size': Optional[int]}]。

        size 直接取自 filer 列举结果(FileSize 或 chunks 之和),避免再对每个文件单独
        发 HEAD（消除 list_structures 等处的 N+1）。解析逻辑与 list_files_recursive 一致。
        """
        results: List[dict] = []
        url = self._get_url(prefix.rstrip('/') + '/')
        params = {'pretty': 'y'}

        entries = []
        async with self._session_cm() as session:
            async with session.get(url, params=params, headers={'Accept': 'application/json'}) as response:
                if response.status != 200:
                    return []
                try:
                    data = await response.json()
                    entries = data.get('Entries', []) or []
                except Exception as e:
                    logger.warning("Error listing entries recursively at %s: %s", prefix, e)
                    return []

        for entry in entries:
            full_path = entry.get('FullPath', '') or entry.get('Name', '')
            if not full_path:
                continue

            name = full_path
            if name.startswith('/buckets/' + self.bucket + '/'):
                name = name[len('/buckets/' + self.bucket + '/'):]

            chunks = entry.get('chunks')
            has_chunks = chunks is not None and isinstance(chunks, list) and len(chunks) > 0
            mode = entry.get('Mode', 0)
            is_dir_mode = (mode & 0o20000000000) != 0 or (mode & 0o40000) != 0
            is_dir = (not has_chunks and is_dir_mode) or name.endswith('/')

            if is_dir:
                results.extend(await self.list_entries_recursive(name))
            else:
                size = entry.get('FileSize')
                if size is None and has_chunks:
                    size = sum(c.get('size', 0) for c in chunks)
                results.append({'path': name, 'size': size})

        logger.debug("Listed %d entries recursively with prefix: %s", len(results), prefix)
        return results

    async def file_exists(self, remote_key: str) -> bool:
        """
        检查文件是否存在
        
        Args:
            remote_key: 远程存储路径
            
        Returns:
            文件是否存在
        """
        url = self._get_url(remote_key)
        
        async with self._session_cm() as session:
            async with session.head(url) as response:
                return response.status == 200
    
    async def copy_file(self, src_key: str, dest_key: str) -> str:
        """
        复制文件（通过下载再上传实现）
        
        Args:
            src_key: 源文件路径
            dest_key: 目标文件路径
            
        Returns:
            目标文件路径
        """
        # Filer API 不直接支持复制，通过下载再上传实现
        data = await self.download_bytes(src_key)
        await self.upload_bytes(data, dest_key)
        
        logger.info("Copied file: %s -> %s", src_key, dest_key)
        return dest_key
    
    async def get_file_stream(self, remote_key: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """
        获取文件流（用于流式下载）
        
        Args:
            remote_key: 远程存储路径
            chunk_size: 分块大小
            
        Yields:
            文件内容分块
        """
        url = self._get_url(remote_key)
        
        async with self._session_cm() as session:
            async with session.get(url) as response:
                if response.status == 404:
                    raise FileNotFoundError(f"File not found: {remote_key}")
                if response.status != 200:
                    text = await response.text()
                    raise Exception(f"Download failed: {response.status} - {text}")
                
                async for chunk in response.content.iter_chunked(chunk_size):
                    yield chunk
    
    async def get_file_info(self, remote_key: str) -> Optional[dict]:
        """
        获取文件元信息
        
        Args:
            remote_key: 远程存储路径
            
        Returns:
            文件信息字典，包含 size, content_type, last_modified 等
        """
        url = self._get_url(remote_key)
        
        async with self._session_cm() as session:
            async with session.head(url) as response:
                if response.status != 200:
                    return None
                
                return {
                    'size': int(response.headers.get('Content-Length', 0)),
                    'content_type': response.headers.get('Content-Type'),
                    'last_modified': response.headers.get('Last-Modified'),
                    'etag': response.headers.get('ETag'),
                }
    
    async def upload_directory(self, local_dir: Path, remote_prefix: str) -> List[str]:
        """
        上传整个目录
        
        Args:
            local_dir: 本地目录路径
            remote_prefix: 远程路径前缀
            
        Returns:
            上传的文件路径列表
        """
        uploaded = []
        for file_path in local_dir.rglob('*'):
            if file_path.is_file():
                relative_path = file_path.relative_to(local_dir)
                remote_key = f"{remote_prefix}/{relative_path}".replace('\\', '/')
                await self.upload_file(file_path, remote_key)
                uploaded.append(remote_key)
        
        logger.info("Uploaded directory %s -> %s (%d files)", 
                   local_dir, remote_prefix, len(uploaded))
        return uploaded
    
    async def download_directory(self, remote_prefix: str, local_dir: Path) -> List[Path]:
        """
        下载整个目录
        
        Args:
            remote_prefix: 远程路径前缀
            local_dir: 本地目录路径
            
        Returns:
            下载的本地文件路径列表
        """
        files = await self.list_files_recursive(remote_prefix)
        downloaded = []
        
        for remote_key in files:
            relative_path = remote_key[len(remote_prefix):].lstrip('/')
            if not relative_path:
                continue
            local_path = local_dir / relative_path
            local_path.parent.mkdir(parents=True, exist_ok=True)
            await self.download_file(remote_key, local_path)
            downloaded.append(local_path)
        
        logger.info("Downloaded directory %s -> %s (%d files)", 
                   remote_prefix, local_dir, len(downloaded))
        return downloaded
    
    async def ensure_bucket_exists(self) -> bool:
        """确保 bucket 目录存在"""
        url = f"{self.filer_endpoint}/buckets/{self.bucket}/"
        
        async with self._session_cm() as session:
            # 检查是否存在
            async with session.head(url) as response:
                if response.status == 200:
                    return True
            
            # 创建目录
            async with session.post(url) as response:
                return response.status in (200, 201)
        
        return False

    async def copy_directory(self, src_prefix: str, dest_prefix: str) -> int:
        """
        复制整个目录（通过列出文件并逐个复制实现）
        
        Args:
            src_prefix: 源目录路径前缀
            dest_prefix: 目标目录路径前缀
            
        Returns:
            成功复制的文件数量
        """
        files = await self.list_files_recursive(src_prefix)
        copied_count = 0
        
        for src_key in files:
            relative_path = src_key[len(src_prefix):].lstrip('/')
            if not relative_path:
                continue
            dest_key = f"{dest_prefix}/{relative_path}"
            try:
                await self.copy_file(src_key, dest_key)
                copied_count += 1
            except Exception as e:
                logger.warning("Failed to copy file %s -> %s: %s", src_key, dest_key, e)
        
        logger.info("Copied directory %s -> %s (%d files)", 
                   src_prefix, dest_prefix, copied_count)
        return copied_count
