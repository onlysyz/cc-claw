"""
CC-Claw Agent Tools - High-frequency utilities for AI agents
"""

import os
import re
import json
import subprocess
import requests
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse


class FileProcessor:
    """File processing utilities"""

    @staticmethod
    def read(path: str, encoding: str = 'utf-8') -> str:
        """Read file content"""
        with open(path, 'r', encoding=encoding) as f:
            return f.read()

    @staticmethod
    def write(path: str, content: str, encoding: str = 'utf-8') -> bool:
        """Write content to file"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding=encoding) as f:
            f.write(content)
        return True

    @staticmethod
    def append(path: str, content: str, encoding: str = 'utf-8') -> bool:
        """Append content to file"""
        with open(path, 'a', encoding=encoding) as f:
            f.write(content)
        return True

    @staticmethod
    def find(pattern: str, path: str = '.', recursive: bool = True) -> List[str]:
        """Find files matching pattern"""
        cmd = f'find {path} -name "{pattern}"' if recursive else f'find {path} -maxdepth 1 -name "{pattern}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return [line for line in result.stdout.strip().split('\n') if line]

    @staticmethod
    def count_lines(path: str) -> int:
        """Count lines in file"""
        with open(path, 'r') as f:
            return sum(1 for _ in f)

    @staticmethod
    def search(pattern: str, path: str = '.', file_type: str = '*') -> List[Dict]:
        """Search for pattern in files using grep"""
        cmd = f'grep -rn --include="*.{file_type}" "{pattern}" {path}'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        matches = []
        for line in result.stdout.strip().split('\n'):
            if ':' in line:
                parts = line.split(':', 2)
                matches.append({
                    'file': parts[0],
                    'line': int(parts[1]) if parts[1].isdigit() else 0,
                    'content': parts[2] if len(parts) > 2 else ''
                })
        return matches


class DataScraper:
    """Web scraping utilities"""

    @staticmethod
    def fetch(url: str, headers: Dict = None, timeout: int = 30) -> Dict:
        """Fetch URL content"""
        default_headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; CC-Claw/1.0)'
        }
        if headers:
            default_headers.update(headers)

        response = requests.get(url, headers=default_headers, timeout=timeout)
        return {
            'status': response.status_code,
            'content': response.text,
            'headers': dict(response.headers),
            'url': response.url
        }

    @staticmethod
    def fetch_json(url: str, headers: Dict = None, timeout: int = 30) -> Any:
        """Fetch and parse JSON"""
        response = requests.get(url, headers=headers, timeout=timeout)
        return response.json()

    @staticmethod
    def extract_links(html: str, base_url: str = '') -> List[str]:
        """Extract all links from HTML"""
        pattern = r'href=["\']([^"\']+)["\']'
        links = re.findall(pattern, html)
        if base_url:
            from urllib.parse import urljoin
            return [urljoin(base_url, link) for link in links]
        return links

    @staticmethod
    def extract_emails(text: str) -> List[str]:
        """Extract email addresses"""
        pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        return re.findall(pattern, text)

    @staticmethod
    def extract_ips(text: str) -> List[str]:
        """Extract IP addresses"""
        pattern = r'\b(?:\d{1,3}\.){3}\d{1,3}\b'
        return list(set(re.findall(pattern, text)))


class ApiClient:
    """API calling utilities"""

    @staticmethod
    def call(
        url: str,
        method: str = 'GET',
        headers: Dict = None,
        params: Dict = None,
        json_data: Dict = None,
        timeout: int = 30
    ) -> Dict:
        """Make HTTP API call"""
        default_headers = {
            'User-Agent': 'CC-Claw/1.0',
            'Accept': 'application/json'
        }
        if headers:
            default_headers.update(headers)

        response = requests.request(
            method=method.upper(),
            url=url,
            headers=default_headers,
            params=params,
            json=json_data,
            timeout=timeout
        )

        try:
            data = response.json()
        except:
            data = {'text': response.text}

        return {
            'status': response.status_code,
            'data': data,
            'headers': dict(response.headers)
        }

    @staticmethod
    def call_with_auth(
        url: str,
        token: str,
        method: str = 'GET',
        headers: Dict = None,
        params: Dict = None,
        json_data: Dict = None,
        timeout: int = 30
    ) -> Dict:
        """Make authenticated API call"""
        auth_headers = {'Authorization': f'Bearer {token}'}
        if headers:
            auth_headers.update(headers)
        return ApiClient.call(url, method, auth_headers, params, json_data, timeout)


class ProcessManager:
    """Process management utilities"""

    @staticmethod
    def list(pattern: str = '') -> List[Dict]:
        """List processes"""
        cmd = 'ps aux' if not pattern else f'ps aux | grep "{pattern}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        processes = []
        lines = result.stdout.strip().split('\n')
        if len(lines) > 1:
            headers = lines[0].split()
            for line in lines[1:]:
                parts = line.split(None, 10)
                if len(parts) >= 11:
                    processes.append({
                        'user': parts[0],
                        'pid': int(parts[1]),
                        'cpu': float(parts[2]),
                        'mem': float(parts[3]),
                        'command': parts[10] if len(parts) > 10 else ''
                    })
        return processes

    @staticmethod
    def kill(pid: int, signal: int = 15) -> bool:
        """Kill a process"""
        try:
            os.kill(pid, signal)
            return True
        except ProcessLookupError:
            return False

    @staticmethod
    def is_running(pattern: str) -> bool:
        """Check if process matching pattern is running"""
        processes = ProcessManager.list(pattern)
        return any('grep' not in p['command'] for p in processes)


class SystemInfo:
    """System information utilities"""

    @staticmethod
    def disk_usage(path: str = '/') -> Dict:
        """Get disk usage"""
        stat = os.statvfs(path)
        total = stat.f_blocks * stat.f_frsize
        free = stat.f_bfree * stat.f_frsize
        used = total - free
        return {
            'total': total,
            'used': used,
            'free': free,
            'percent': round((used / total) * 100, 1) if total > 0 else 0
        }

    @staticmethod
    def memory() -> Dict:
        """Get memory usage"""
        with open('/proc/meminfo', 'r') as f:
            lines = f.readlines()
        mem = {}
        for line in lines:
            if ':' in line:
                key, val = line.split(':')
                mem[key.strip()] = val.strip()
        return mem

    @staticmethod
    def cpu_load() -> Dict:
        """Get CPU load"""
        with open('/proc/loadavg', 'r') as f:
            avg = f.read().split()[:3]
        return {
            '1min': float(avg[0]),
            '5min': float(avg[1]),
            '15min': float(avg[2])
        }


class GitHelper:
    """Git utilities"""

    @staticmethod
    def status() -> str:
        """Get git status"""
        result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
        return result.stdout.strip()

    @staticmethod
    def diff(file: str = '') -> str:
        """Get git diff"""
        cmd = ['git', 'diff', file] if file else ['git', 'diff']
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout

    @staticmethod
    def log(limit: int = 10) -> List[Dict]:
        """Get git log"""
        cmd = ['git', 'log', f'--pretty=format:%h|%s|%an|%ad', f'-{limit}', '--date=iso']
        result = subprocess.run(cmd, capture_output=True, text=True)
        commits = []
        for line in result.stdout.strip().split('\n'):
            if '|' in line:
                parts = line.split('|')
                if len(parts) >= 4:
                    commits.append({
                        'hash': parts[0],
                        'message': parts[1],
                        'author': parts[2],
                        'date': parts[3]
                    })
        return commits

    @staticmethod
    def branch() -> str:
        """Get current branch"""
        result = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True)
        return result.stdout.strip()


class DockerHelper:
    """Docker utilities"""

    @staticmethod
    def ps(all: bool = False) -> List[Dict]:
        """List containers"""
        cmd = ['docker', 'ps', '--format', '{{.ID}}|{{.Names}}|{{.Status}}|{{.Image}}']
        if all:
            cmd.insert(2, '-a')
        result = subprocess.run(cmd, capture_output=True, text=True)
        containers = []
        for line in result.stdout.strip().split('\n'):
            if '|' in line:
                parts = line.split('|')
                containers.append({
                    'id': parts[0],
                    'name': parts[1],
                    'status': parts[2],
                    'image': parts[3]
                })
        return containers

    @staticmethod
    def logs(container: str, lines: int = 50) -> str:
        """Get container logs"""
        cmd = ['docker', 'logs', '--tail', str(lines), container]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout + result.stderr

    @staticmethod
    def restart(container: str) -> bool:
        """Restart container"""
        result = subprocess.run(['docker', 'restart', container], capture_output=True)
        return result.returncode == 0

    @staticmethod
    def status() -> Dict:
        """Get Docker system status"""
        result = subprocess.run(['docker', 'system', 'df', '--format', '{{.Type}}|{{.Total}}|{{.Size}}'],
                                capture_output=True, text=True)
        info = {'images': 0, 'containers': 0, 'volumes': 0}
        for line in result.stdout.strip().split('\n'):
            if '|' in line:
                parts = line.split('|')
                if len(parts) >= 3:
                    t = parts[0].lower()
                    if t in info:
                        info[t] = {'total': int(parts[1]), 'size': parts[2]}
        return info


# Tool registry for CC-Claw
TOOLS = {
    'file': FileProcessor,
    'scraper': DataScraper,
    'api': ApiClient,
    'process': ProcessManager,
    'system': SystemInfo,
    'git': GitHelper,
    'docker': DockerHelper,
}


def get_tool(name: str):
    """Get tool by name"""
    return TOOLS.get(name.lower())
