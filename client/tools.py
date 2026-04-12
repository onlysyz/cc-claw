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


class DatabaseTool:
    """SQLite database utilities"""

    @staticmethod
    def query(db_path: str, sql: str) -> List[Dict]:
        """Execute SQL query and return results"""
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql)

            if sql.strip().upper().startswith('SELECT'):
                rows = cursor.fetchall()
                result = [dict(row) for row in rows]
            else:
                conn.commit()
                result = [{'affected_rows': cursor.rowcount}]

            conn.close()
            return result
        except Exception as e:
            return [{'error': str(e)}]

    @staticmethod
    def execute(db_path: str, sql: str) -> Dict:
        """Execute SQL statement (INSERT/UPDATE/DELETE)"""
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(sql)
            conn.commit()
            result = {
                'rowcount': cursor.rowcount,
                'lastrowid': cursor.lastrowid
            }
            conn.close()
            return result
        except Exception as e:
            return {'error': str(e)}

    @staticmethod
    def list_tables(db_path: str) -> List[str]:
        """List all tables in database"""
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            return tables
        except Exception as e:
            return [str(e)]

    @staticmethod
    def table_info(db_path: str, table: str) -> List[Dict]:
        """Get table schema"""
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table})")
            result = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return result
        except Exception as e:
            return [{'error': str(e)}]

    @staticmethod
    def create_table(db_path: str, table: str, columns: Dict) -> bool:
        """Create table with columns {name: type}"""
        try:
            import sqlite3
            cols = ', '.join([f"{k} {v}" for k, v in columns.items()])
            sql = f"CREATE TABLE IF NOT EXISTS {table} ({cols})"
            conn = sqlite3.connect(db_path)
            conn.execute(sql)
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            return False


class ImageTool:
    """Image processing utilities"""

    @staticmethod
    def info(path: str) -> Dict:
        """Get image info (dimensions, format, size)"""
        try:
            from PIL import Image
            img = Image.open(path)
            return {
                'width': img.width,
                'height': img.height,
                'format': img.format,
                'mode': img.mode,
                'size_bytes': os.path.getsize(path)
            }
        except Exception as e:
            return {'error': str(e)}

    @staticmethod
    def resize(path: str, output: str, width: int, height: int) -> bool:
        """Resize image to dimensions"""
        try:
            from PIL import Image
            img = Image.open(path)
            resized = img.resize((width, height), Image.Resampling.LANCZOS)
            resized.save(output)
            return True
        except Exception as e:
            return False

    @staticmethod
    def thumbnail(path: str, output: str, max_size: int = 256) -> bool:
        """Create thumbnail"""
        try:
            from PIL import Image
            img = Image.open(path)
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            img.save(output)
            return True
        except Exception as e:
            return False

    @staticmethod
    def convert(input_path: str, output_path: str, format: str = 'PNG') -> bool:
        """Convert image format (JPEG, PNG, WEBP, etc.)"""
        try:
            from PIL import Image
            img = Image.open(input_path)
            if format.upper() == 'JPEG' and img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            img.save(output_path, format=format.upper())
            return True
        except Exception as e:
            return False

    @staticmethod
    def compress(path: str, output: str, quality: int = 85) -> bool:
        """Compress image (JPEG)"""
        try:
            from PIL import Image
            img = Image.open(path)
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            img.save(output, 'JPEG', quality=quality, optimize=True)
            return True
        except Exception as e:
            return False


class NotificationTool:
    """Notification utilities (Email, Push)"""

    @staticmethod
    def send_email(
        to: str,
        subject: str,
        body: str,
        smtp_host: str = 'localhost',
        smtp_port: int = 25,
        from_addr: str = 'cc-claw@localhost'
    ) -> Dict:
        """Send email notification"""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            msg = MIMEMultipart()
            msg['From'] = from_addr
            msg['To'] = to
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.send_message(msg)

            return {'success': True, 'to': to}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    def push(title: str, body: str, priority: str = 'normal') -> Dict:
        """Send push notification via local notify-send or Slack webhook"""
        try:
            # Try notify-send (Linux)
            if os.path.exists('/usr/bin/notify-send'):
                urgency = 'low' if priority == 'low' else ('critical' if priority == 'high' else 'normal')
                subprocess.run(['notify-send', '-u', urgency, title, body])
                return {'success': True, 'method': 'notify-send'}

            # Try terminal-notifier (macOS)
            if os.path.exists('/usr/local/bin/terminal-notifier'):
                subprocess.run(['terminal-notifier', '-title', title, '-message', body])
                return {'success': True, 'method': 'terminal-notifier'}

            return {'success': False, 'error': 'No notification tool available'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    def slack_webhook(webhook_url: str, text: str, channel: str = '') -> Dict:
        """Send Slack notification via webhook"""
        try:
            payload = {'text': text}
            if channel:
                payload['channel'] = channel
            response = requests.post(
                webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            return {'success': response.status_code == 200, 'status': response.status_code}
        except Exception as e:
            return {'success': False, 'error': str(e)}


class CodeAnalysisTool:
    """Static code analysis utilities"""

    @staticmethod
    def count_lines(path: str, extensions: str = 'py,js,ts,java,cpp,c,go,rs') -> Dict:
        """Count lines of code by language"""
        try:
            exts = extensions.split(',')
            total = 0
            by_lang = {}

            for root, dirs, files in os.walk(path):
                # Skip common non-code directories
                dirs[:] = [d for d in dirs if d not in ['node_modules', '__pycache__', '.git', 'venv', 'env', 'dist', 'build']]

                for file in files:
                    if any(file.endswith(f'.{ext}') for ext in exts):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                lines = len(f.readlines())
                            total += lines
                            ext = os.path.splitext(file)[1][1:]
                            by_lang[ext] = by_lang.get(ext, 0) + lines
                        except:
                            pass

            return {'total': total, 'by_language': by_lang}
        except Exception as e:
            return {'error': str(e)}

    @staticmethod
    def find_functions(path: str, language: str = 'python') -> List[Dict]:
        """Find function definitions in code"""
        patterns = {
            'python': r'def\s+(\w+)\s*\(([^)]*)\)',
            'javascript': r'(?:function\s+(\w+)\s*\(([^)]*)\)|const\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)',
            'java': r'(?:public|private|protected)\s+(?:static\s+)?(?:void|int|String|\w+)\s+(\w+)\s*\(([^)]*)\)',
            'go': r'func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(([^)]*)\)',
        }

        try:
            pattern = patterns.get(language.lower(), patterns['python'])
            results = []

            for root, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if d not in ['node_modules', '__pycache__', '.git', 'venv']]

                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            for i, line in enumerate(f, 1):
                                match = re.search(pattern, line)
                                if match:
                                    name = match.group(1)
                                    params = match.group(2) if match.lastindex >= 2 else ''
                                    results.append({
                                        'file': file_path,
                                        'line': i,
                                        'name': name,
                                        'params': params.strip()
                                    })
                    except:
                        pass

            return results
        except Exception as e:
            return [{'error': str(e)}]

    @staticmethod
    def complexity(path: str, language: str = 'python') -> Dict:
        """Estimate code complexity (cyclomatic approximation)"""
        try:
            keywords = ['if', 'elif', 'else', 'for', 'while', 'and', 'or', 'try', 'except', 'with']
            total_complexity = 0
            files_analyzed = 0

            for root, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if d not in ['node_modules', '__pycache__', '.git', 'venv']]

                for file in files:
                    if file.endswith(f'.{language}'):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                            complexity = 1 + sum(content.count(kw) for kw in keywords)
                            total_complexity += complexity
                            files_analyzed += 1
                        except:
                            pass

            return {
                'total_complexity': total_complexity,
                'files_analyzed': files_analyzed,
                'avg_complexity': round(total_complexity / files_analyzed, 1) if files_analyzed > 0 else 0
            }
        except Exception as e:
            return {'error': str(e)}

    @staticmethod
    def dependencies(path: str) -> Dict:
        """Analyze code dependencies (imports/requires)"""
        try:
            imports = {}

            for root, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if d not in ['node_modules', '__pycache__', '.git', 'venv']]

                for file in files:
                    if file.endswith(('.py', '.js', '.ts', '.go')):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()

                            if file.endswith('.py'):
                                # Python imports
                                py_imports = re.findall(r'^(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))', content, re.MULTILINE)
                                for imp in py_imports:
                                    mod = imp[0] or imp[1]
                                    imports[mod] = imports.get(mod, 0) + 1
                            elif file.endswith(('.js', '.ts')):
                                # JS/TS imports
                                js_imports = re.findall(r'(?:require\([\'"]([^\'"]+)[\'"]\)|from\s+[\'"]([^\'"]+)[\'"]\s+import)', content)
                                for imp in js_imports:
                                    mod = imp[0] or imp[1]
                                    imports[mod] = imports.get(mod, 0) + 1
                        except:
                            pass

            # Sort by frequency
            sorted_imports = dict(sorted(imports.items(), key=lambda x: x[1], reverse=True)[:50])
            return {'dependencies': sorted_imports, 'total_unique': len(imports)}
        except Exception as e:
            return {'error': str(e)}


class MonitorTool:
    """System monitoring with alerting"""

    @staticmethod
    def check_disk(threshold: int = 90) -> Dict:
        """Check disk usage and alert if threshold exceeded"""
        usage = SystemInfo.disk_usage('/')
        percent = usage.get('percent', 0)
        return {
            'alert': percent >= threshold,
            'percent': percent,
            'total_gb': round(usage.get('total', 0) / (1024**3), 2),
            'free_gb': round(usage.get('free', 0) / (1024**3), 2),
            'threshold': threshold
        }

    @staticmethod
    def check_memory(threshold: int = 90) -> Dict:
        """Check memory usage and alert if threshold exceeded"""
        mem = SystemInfo.memory()

        # Parse /proc/meminfo values (in KB)
        total = int(mem.get('MemTotal', '0').split()[0]) if 'MemTotal' in mem else 0
        available = int(mem.get('MemAvailable', mem.get('MemFree', '0')).split()[0]) if 'MemAvailable' in mem or 'MemFree' in mem else 0
        used = total - available

        if total > 0:
            percent = round((used / total) * 100, 1)
        else:
            percent = 0

        return {
            'alert': percent >= threshold,
            'percent': percent,
            'total_mb': round(total / 1024, 2),
            'used_mb': round(used / 1024, 2),
            'free_mb': round(available / 1024, 2),
            'threshold': threshold
        }

    @staticmethod
    def check_cpu(threshold: float = 80.0) -> Dict:
        """Check CPU load and alert if threshold exceeded"""
        load = SystemInfo.cpu_load()
        load_1min = load.get('1min', 0)

        return {
            'alert': load_1min >= threshold,
            'load_1min': load_1min,
            'load_5min': load.get('5min', 0),
            'load_15min': load.get('15min', 0),
            'threshold': threshold
        }

    @staticmethod
    def check_port(port: int, host: str = 'localhost') -> Dict:
        """Check if a port is open"""
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        try:
            result = sock.connect_ex((host, port))
            sock.close()
            return {'port_open': result == 0, 'port': port, 'host': host}
        except Exception as e:
            return {'port_open': False, 'port': port, 'host': host, 'error': str(e)}

    @staticmethod
    def check_url(url: str, timeout: int = 10) -> Dict:
        """Check if URL is reachable"""
        try:
            response = requests.get(url, timeout=timeout)
            return {
                'reachable': True,
                'status': response.status_code,
                'url': url,
                'response_time_ms': int(response.elapsed.total_seconds() * 1000)
            }
        except Exception as e:
            return {
                'reachable': False,
                'url': url,
                'error': str(e)
            }

    @staticmethod
    def health_check(port: int = 3000) -> Dict:
        """Run comprehensive health check"""
        return {
            'disk': MonitorTool.check_disk(),
            'memory': MonitorTool.check_memory(),
            'cpu': MonitorTool.check_cpu(),
            'port_open': MonitorTool.check_port(port),
        }


# Tool registry for CC-Claw
TOOLS = {
    'file': FileProcessor,
    'scraper': DataScraper,
    'api': ApiClient,
    'process': ProcessManager,
    'system': SystemInfo,
    'git': GitHelper,
    'docker': DockerHelper,
    'database': DatabaseTool,
    'image': ImageTool,
    'notification': NotificationTool,
    'code_analysis': CodeAnalysisTool,
    'monitor': MonitorTool,
}


def get_tool(name: str):
    """Get tool by name"""
    return TOOLS.get(name.lower())
