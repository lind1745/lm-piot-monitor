import sqlite3
import json
from datetime import datetime
from contextlib import contextmanager
import time
import os

DATABASE = 'instance/servers.db'
MAX_RETRIES = 5
RETRY_DELAY = 0.1

@contextmanager
def get_db():
    """Получение соединения с БД с повторными попытками при блокировке"""
    last_exception = None
    
    for attempt in range(MAX_RETRIES):
        try:
            os.makedirs('instance', exist_ok=True)
            
            conn = sqlite3.connect(DATABASE, timeout=30.0)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.execute('PRAGMA cache_size=-10000')
            try:
                yield conn
                conn.commit()
            finally:
                conn.close()
            return
        except sqlite3.OperationalError as e:
            last_exception = e
            if "database is locked" in str(e) and attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
                continue
            raise
    if last_exception:
        raise last_exception

def init_db():
    """Инициализация базы данных с раздельными IP для сервисов"""
    with get_db() as conn:
        # Основная таблица серверов (магазинов)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS servers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                ip_lmhz TEXT NOT NULL,
                ip_piot TEXT,
                port_lmhz INTEGER DEFAULT 5995,
                port_lm INTEGER DEFAULT 5063,
                port_piot INTEGER DEFAULT 51077,
                enabled BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_check TIMESTAMP
            )
        ''')
        
        # Таблица для сервиса ЛМЧЗ
        conn.execute('''
            CREATE TABLE IF NOT EXISTS lmhz_status (
                server_id INTEGER PRIMARY KEY,
                url TEXT,
                status TEXT,
                version TEXT,
                error TEXT,
                last_check TIMESTAMP,
                FOREIGN KEY (server_id) REFERENCES servers(id) ON DELETE CASCADE
            )
        ''')
        
        # Таблица для сервиса ЛМ (Контроллер ЛМ)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS lm_status (
                server_id INTEGER PRIMARY KEY,
                url TEXT,
                status TEXT,
                version TEXT,
                error TEXT,
                last_check TIMESTAMP,
                FOREIGN KEY (server_id) REFERENCES servers(id) ON DELETE CASCADE
            )
        ''')
        
        # Таблица для сервиса ПИОТ
        conn.execute('''
            CREATE TABLE IF NOT EXISTS piot_status (
                server_id INTEGER PRIMARY KEY,
                url TEXT,
                status TEXT,
                version TEXT,
                error TEXT,
                license_until TEXT,
                last_check TIMESTAMP,
                FOREIGN KEY (server_id) REFERENCES servers(id) ON DELETE CASCADE
            )
        ''')
        
        # Индексы
        conn.execute('CREATE INDEX IF NOT EXISTS idx_lmhz_status ON lmhz_status(status)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_lm_status ON lm_status(status)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_piot_status ON piot_status(status)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_servers_ip_lmhz ON servers(ip_lmhz)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_servers_ip_piot ON servers(ip_piot)')

def add_server(name, ip_lmhz, ip_piot=None, port_lmhz=5995, port_lm=5063, port_piot=51077):
    """Добавление нового сервера с раздельными IP"""
    with get_db() as conn:
        try:
            # Если IP для ПИОТ не указан, используем IP ЛМЧЗ
            if not ip_piot:
                ip_piot = ip_lmhz
            
            cursor = conn.execute('''
                INSERT INTO servers (name, ip_lmhz, ip_piot, port_lmhz, port_lm, port_piot) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, ip_lmhz, ip_piot, port_lmhz, port_lm, port_piot))
            server_id = cursor.lastrowid
            
            # Создаем записи для всех трех сервисов
            lmhz_url = f"http://{ip_lmhz}:{port_lmhz}/api/v2/status"
            lm_url = f"http://{ip_lmhz}:{port_lm}/api/v1/service-info"
            piot_url = f"http://{ip_piot}:{port_piot}/api/v1/instances/info"
            
            conn.execute(
                'INSERT INTO lmhz_status (server_id, url) VALUES (?, ?)',
                (server_id, lmhz_url)
            )
            conn.execute(
                'INSERT INTO lm_status (server_id, url) VALUES (?, ?)',
                (server_id, lm_url)
            )
            conn.execute(
                'INSERT INTO piot_status (server_id, url) VALUES (?, ?)',
                (server_id, piot_url)
            )
            
            return server_id
        except sqlite3.IntegrityError as e:
            print(f"Error adding server: {e}")
            return None

def get_all_servers():
    """Получение всех серверов со статусами"""
    with get_db() as conn:
        servers = conn.execute('''
            SELECT 
                s.id, s.name, s.ip_lmhz, s.ip_piot, s.port_lmhz, s.port_lm, s.port_piot, s.enabled,
                s.created_at, s.updated_at, s.last_check,
                IFNULL(l.status, 'unknown') as lmhz_status, 
                l.version as lmhz_version, 
                l.error as lmhz_error,
                IFNULL(lm.status, 'unknown') as lm_status, 
                lm.version as lm_version, 
                lm.error as lm_error,
                IFNULL(p.status, 'unknown') as piot_status, 
                p.version as piot_version, 
                p.error as piot_error,
                p.license_until as piot_license_until
            FROM servers s
            LEFT JOIN lmhz_status l ON s.id = l.server_id
            LEFT JOIN lm_status lm ON s.id = lm.server_id
            LEFT JOIN piot_status p ON s.id = p.server_id
            ORDER BY s.id
        ''').fetchall()
        
        result = []
        for row in servers:
            server = dict(row)
            server['services'] = {
                'lmhz': {
                    'status': server.pop('lmhz_status'),
                    'version': server.pop('lmhz_version'),
                    'error': server.pop('lmhz_error')
                },
                'lm': {
                    'status': server.pop('lm_status'),
                    'version': server.pop('lm_version'),
                    'error': server.pop('lm_error')
                },
                'piot': {
                    'status': server.pop('piot_status'),
                    'version': server.pop('piot_version'),
                    'error': server.pop('piot_error'),
                    'license_until': server.pop('piot_license_until')
                }
            }
            result.append(server)
        return result

def get_server(server_id):
    """Получение одного сервера по ID"""
    with get_db() as conn:
        server = conn.execute('''
            SELECT 
                s.id, s.name, s.ip_lmhz, s.ip_piot, s.port_lmhz, s.port_lm, s.port_piot, s.enabled,
                s.created_at, s.updated_at, s.last_check,
                l.status as lmhz_status, l.version as lmhz_version, l.error as lmhz_error,
                lm.status as lm_status, lm.version as lm_version, lm.error as lm_error,
                p.status as piot_status, p.version as piot_version, p.error as piot_error,
                p.license_until as piot_license_until
            FROM servers s
            LEFT JOIN lmhz_status l ON s.id = l.server_id
            LEFT JOIN lm_status lm ON s.id = lm.server_id
            LEFT JOIN piot_status p ON s.id = p.server_id
            WHERE s.id = ?
        ''', (server_id,)).fetchone()
        
        if server:
            server_dict = dict(server)
            server_dict['services'] = {
                'lmhz': {
                    'status': server_dict.pop('lmhz_status'),
                    'version': server_dict.pop('lmhz_version'),
                    'error': server_dict.pop('lmhz_error')
                },
                'lm': {
                    'status': server_dict.pop('lm_status'),
                    'version': server_dict.pop('lm_version'),
                    'error': server_dict.pop('lm_error')
                },
                'piot': {
                    'status': server_dict.pop('piot_status'),
                    'version': server_dict.pop('piot_version'),
                    'error': server_dict.pop('piot_error'),
                    'license_until': server_dict.pop('piot_license_until')
                }
            }
            return server_dict
        return None

def update_server(server_id, name=None, ip_lmhz=None, ip_piot=None, 
                  port_lmhz=None, port_lm=None, port_piot=None, enabled=None):
    """Обновление параметров сервера"""
    with get_db() as conn:
        updates = []
        params = []
        
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        
        if ip_lmhz is not None:
            updates.append("ip_lmhz = ?")
            params.append(ip_lmhz)
        
        if ip_piot is not None:
            updates.append("ip_piot = ?")
            params.append(ip_piot)
        
        if port_lmhz is not None:
            updates.append("port_lmhz = ?")
            params.append(port_lmhz)
        
        if port_lm is not None:
            updates.append("port_lm = ?")
            params.append(port_lm)
        
        if port_piot is not None:
            updates.append("port_piot = ?")
            params.append(port_piot)
        
        if enabled is not None:
            updates.append("enabled = ?")
            params.append(1 if enabled else 0)
        
        if updates:
            params.append(server_id)
            conn.execute(f'UPDATE servers SET {", ".join(updates)} WHERE id = ?', params)
            
            # Обновляем URL для сервисов
            current = conn.execute('SELECT ip_lmhz, ip_piot, port_lmhz, port_lm, port_piot FROM servers WHERE id = ?', (server_id,)).fetchone()
            if current:
                lmhz_url = f"http://{current['ip_lmhz']}:{current['port_lmhz']}/api/v2/status"
                lm_url = f"http://{current['ip_lmhz']}:{current['port_lm']}/api/v1/service-info"
                piot_url = f"http://{current['ip_piot']}:{current['port_piot']}/api/v1/instances/info"
                
                conn.execute('UPDATE lmhz_status SET url = ? WHERE server_id = ?', (lmhz_url, server_id))
                conn.execute('UPDATE lm_status SET url = ? WHERE server_id = ?', (lm_url, server_id))
                conn.execute('UPDATE piot_status SET url = ? WHERE server_id = ?', (piot_url, server_id))

def update_service_status(server_id, service, status, version, error=None, license_until=None):
    """Обновление статуса конкретного сервиса"""
    table_map = {
        'lmhz': 'lmhz_status',
        'lm': 'lm_status',
        'piot': 'piot_status'
    }
    
    table = table_map.get(service)
    if not table:
        return False
    
    with get_db() as conn:
        if service == 'piot':
            conn.execute(f'''
                UPDATE {table}
                SET status = ?, version = ?, error = ?, license_until = ?, last_check = CURRENT_TIMESTAMP
                WHERE server_id = ?
            ''', (status, version, error, license_until, server_id))
        else:
            conn.execute(f'''
                UPDATE {table}
                SET status = ?, version = ?, error = ?, last_check = CURRENT_TIMESTAMP
                WHERE server_id = ?
            ''', (status, version, error, server_id))
        
        conn.execute('''
            UPDATE servers
            SET last_check = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (server_id,))
    
    return True

def get_stats():
    """Получение статистики по всем сервисам"""
    with get_db() as conn:
        stats = {}
        
        result = conn.execute('SELECT COUNT(*) as count FROM servers WHERE enabled = 1').fetchone()
        stats['total'] = result['count'] if result else 0
        
        lmhz_total = conn.execute(
            'SELECT COUNT(*) as count FROM lmhz_status l JOIN servers s ON l.server_id = s.id WHERE s.enabled = 1'
        ).fetchone()
        lmhz_total = lmhz_total['count'] if lmhz_total else 0
        
        lmhz_ready = conn.execute(
            'SELECT COUNT(*) as count FROM lmhz_status l JOIN servers s ON l.server_id = s.id WHERE s.enabled = 1 AND l.status = "ready"'
        ).fetchone()
        lmhz_ready = lmhz_ready['count'] if lmhz_ready else 0
        
        stats['lmhz'] = {
            'ready': lmhz_ready,
            'error': lmhz_total - lmhz_ready
        }
        
        lm_total = conn.execute(
            'SELECT COUNT(*) as count FROM lm_status l JOIN servers s ON l.server_id = s.id WHERE s.enabled = 1'
        ).fetchone()
        lm_total = lm_total['count'] if lm_total else 0
        
        lm_ready = conn.execute(
            'SELECT COUNT(*) as count FROM lm_status l JOIN servers s ON l.server_id = s.id WHERE s.enabled = 1 AND l.status = "ready"'
        ).fetchone()
        lm_ready = lm_ready['count'] if lm_ready else 0
        
        stats['lm'] = {
            'ready': lm_ready,
            'error': lm_total - lm_ready
        }
        
        piot_total = conn.execute(
            'SELECT COUNT(*) as count FROM piot_status p JOIN servers s ON p.server_id = s.id WHERE s.enabled = 1'
        ).fetchone()
        piot_total = piot_total['count'] if piot_total else 0
        
        piot_ready = conn.execute(
            'SELECT COUNT(*) as count FROM piot_status p JOIN servers s ON p.server_id = s.id WHERE s.enabled = 1 AND p.status = "ready"'
        ).fetchone()
        piot_ready = piot_ready['count'] if piot_ready else 0
        
        stats['piot'] = {
            'ready': piot_ready,
            'error': piot_total - piot_ready
        }
        
        return stats

def delete_server(server_id):
    """Удаление сервера"""
    with get_db() as conn:
        conn.execute('DELETE FROM servers WHERE id = ?', (server_id,))

def import_from_json(json_data):
    """Импорт серверов из JSON с поддержкой двух IP"""
    count = 0
    with get_db() as conn:
        for item in json_data:
            try:
                name = item.get('name', '')
                ip_lmhz = item.get('ip_lmhz') or item.get('ip_address') or item.get('ip')
                ip_piot = item.get('ip_piot', ip_lmhz)
                
                if not ip_lmhz:
                    continue
                
                port_lmhz = item.get('port_lmhz', 5995)
                port_lm = item.get('port_lm', 5063)
                port_piot = item.get('port_piot', 51077)
                
                exists = conn.execute(
                    'SELECT id FROM servers WHERE ip_lmhz = ? AND ip_piot = ?', (ip_lmhz, ip_piot)
                ).fetchone()
                
                if not exists:
                    cursor = conn.execute('''
                        INSERT INTO servers (name, ip_lmhz, ip_piot, port_lmhz, port_lm, port_piot) 
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (name, ip_lmhz, ip_piot, port_lmhz, port_lm, port_piot))
                    server_id = cursor.lastrowid
                    
                    lmhz_url = f"http://{ip_lmhz}:{port_lmhz}/api/v2/status"
                    lm_url = f"http://{ip_lmhz}:{port_lm}/api/v1/service-info"
                    piot_url = f"http://{ip_piot}:{port_piot}/api/v1/instances/info"
                    
                    conn.execute('INSERT INTO lmhz_status (server_id, url) VALUES (?, ?)', (server_id, lmhz_url))
                    conn.execute('INSERT INTO lm_status (server_id, url) VALUES (?, ?)', (server_id, lm_url))
                    conn.execute('INSERT INTO piot_status (server_id, url) VALUES (?, ?)', (server_id, piot_url))
                    
                    count += 1
            except Exception as e:
                print(f"Error importing: {e}")
    return count