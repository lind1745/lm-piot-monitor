from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import database as db
import os

app = Flask(__name__)
CORS(app)

db.init_db()
executor = ThreadPoolExecutor(max_workers=20)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/servers', methods=['GET'])
def get_servers():
    try:
        servers = db.get_all_servers()
        return jsonify(servers)
    except Exception as e:
        print(f"Error getting servers: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/servers', methods=['POST'])
def add_server():
    """Добавление нового сервера с двумя IP"""
    data = request.json
    name = data.get('name')
    ip_lmhz = data.get('ip_lmhz')
    ip_piot = data.get('ip_piot', ip_lmhz)
    port_lmhz = data.get('port_lmhz', 5995)
    port_lm = data.get('port_lm', 5063)
    port_piot = data.get('port_piot', 51077)
    
    if not name:
        name = ip_lmhz
    
    server_id = db.add_server(name, ip_lmhz, ip_piot, port_lmhz, port_lm, port_piot)
    
    if server_id:
        return jsonify({'success': True, 'id': server_id, 'message': 'Сервер добавлен'})
    else:
        return jsonify({'success': False, 'message': 'Ошибка добавления сервера'}), 400

@app.route('/api/servers/<int:server_id>', methods=['PUT'])
def update_server(server_id):
    """Обновление сервера с двумя IP"""
    data = request.json
    db.update_server(
        server_id,
        name=data.get('name'),
        ip_lmhz=data.get('ip_lmhz'),
        ip_piot=data.get('ip_piot'),
        port_lmhz=data.get('port_lmhz'),
        port_lm=data.get('port_lm'),
        port_piot=data.get('port_piot'),
        enabled=data.get('enabled')
    )
    return jsonify({'success': True, 'message': 'Сервер обновлен'})

@app.route('/api/servers/<int:server_id>', methods=['DELETE'])
def delete_server(server_id):
    db.delete_server(server_id)
    return jsonify({'success': True, 'message': 'Сервер удален'})

def check_single_service(server, service):
    """Проверка одного сервиса на сервере"""
    
    if service == 'piot':
        # ПИОТ использует ip_piot
        url = f"http://{server['ip_piot']}:{server['port_piot']}/api/v1/instances/info"
        
        try:
            response = requests.get(url, timeout=8, headers={'Accept': 'application/json'})
            
            if response.status_code == 200:
                data = response.json()
                instances = data.get('instances', [])
                
                if instances and len(instances) > 0:
                    service_state = instances[0].get('serviceState', 'unknown')
                    instance_id = instances[0].get('id', None)
                    version = instances[0].get('version', None)
                    
                    if service_state == 'Работает':
                        status = 'ready'
                    else:
                        status = 'error'
                    
                    license_until = None
                    
                    if instance_id:
                        license_url = f"http://{server['ip_piot']}:{server['port_piot']}/api/v1/instances/info/{instance_id}"
                        try:
                            license_response = requests.get(license_url, timeout=8, headers={'Accept': 'application/json'})
                            if license_response.status_code == 200:
                                license_data = license_response.json()
                                licenses = license_data.get('licenses', [])
                                if licenses and len(licenses) > 0:
                                    license_until = licenses[0].get('activeTill', None)
                        except Exception as e:
                            print(f"License check error for {server['ip_piot']}: {e}")
                    
                    return {
                        'service': service, 
                        'success': True, 
                        'status': status, 
                        'version': version, 
                        'license_until': license_until,
                        'error': None
                    }
                else:
                    return {'service': service, 'success': False, 'status': 'error', 'version': None, 'error': 'Нет данных об инстансах'}
            else:
                return {'service': service, 'success': False, 'status': 'error', 'version': None, 'error': f"HTTP {response.status_code}"}
                
        except requests.Timeout:
            return {'service': service, 'success': False, 'status': 'error', 'version': None, 'error': "Timeout (8s)"}
        except Exception as e:
            return {'service': service, 'success': False, 'status': 'error', 'version': None, 'error': str(e)}
    
    elif service == 'lm':
        # ЛМ использует ip_lmhz
        url = f"http://{server['ip_lmhz']}:{server['port_lm']}/api/v1/service-info"
        
        try:
            response = requests.get(url, timeout=8, headers={'Accept': 'application/json'})
            
            if response.status_code == 200:
                data = response.json()
                version = data.get('version') or data.get('Version')
                if version:
                    return {'service': service, 'success': True, 'status': 'ready', 'version': version, 'error': None}
                else:
                    return {'service': service, 'success': False, 'status': 'error', 'version': None, 'error': 'Нет версии в ответе'}
            else:
                return {'service': service, 'success': False, 'status': 'error', 'version': None, 'error': f"HTTP {response.status_code}"}
                
        except requests.Timeout:
            return {'service': service, 'success': False, 'status': 'error', 'version': None, 'error': "Timeout (8s)"}
        except Exception as e:
            return {'service': service, 'success': False, 'status': 'error', 'version': None, 'error': str(e)}
    
    else:
        # ЛМЧЗ использует ip_lmhz
        url = f"http://{server['ip_lmhz']}:{server['port_lmhz']}/api/v2/status"
        
        try:
            response = requests.get(url, timeout=8, headers={'Accept': 'application/json'})
            
            if response.status_code == 200:
                data = response.json()
                status = data.get('status', data.get('Status', 'unknown'))
                version = data.get('version', data.get('Version', None))
                if status == 'ready':
                    return {'service': service, 'success': True, 'status': 'ready', 'version': version, 'error': None}
                else:
                    return {'service': service, 'success': False, 'status': 'error', 'version': version, 'error': f'Статус: {status}'}
            else:
                return {'service': service, 'success': False, 'status': 'error', 'version': None, 'error': f"HTTP {response.status_code}"}
                
        except requests.Timeout:
            return {'service': service, 'success': False, 'status': 'error', 'version': None, 'error': "Timeout (8s)"}
        except Exception as e:
            return {'service': service, 'success': False, 'status': 'error', 'version': None, 'error': str(e)}

@app.route('/api/servers/<int:server_id>/check-all', methods=['POST'])
def check_all_services(server_id):
    server = db.get_server(server_id)
    
    if not server:
        return jsonify({'error': 'Server not found'}), 404
    
    results = {}
    futures = []
    
    for service in ['lmhz', 'lm', 'piot']:
        future = executor.submit(check_single_service, server, service)
        futures.append(future)
    
    for future in as_completed(futures):
        result = future.result()
        service = result['service']
        if result['success']:
            if service == 'piot':
                db.update_service_status(server_id, service, 'ready', result.get('version'), None, result.get('license_until'))
                results[service] = {
                    'success': True,
                    'status': 'ready',
                    'version': result.get('version'),
                    'license_until': result.get('license_until')
                }
            else:
                db.update_service_status(server_id, service, 'ready', result.get('version'), None)
                results[service] = {
                    'success': True,
                    'status': 'ready',
                    'version': result.get('version')
                }
        else:
            db.update_service_status(server_id, service, 'error', None, result.get('error'))
            results[service] = {
                'success': False,
                'status': 'error',
                'error': result.get('error')
            }
    
    return jsonify(results)

@app.route('/api/servers/check-all', methods=['POST'])
def check_all_servers_all_services():
    servers = db.get_all_servers()
    enabled_servers = [s for s in servers if s['enabled']]
    
    all_futures = []
    
    for server in enabled_servers:
        for service in ['lmhz', 'lm', 'piot']:
            future = executor.submit(check_single_service, server, service)
            all_futures.append((future, server['id'], service))
    
    results_dict = {}
    
    for future, server_id, service in all_futures:
        try:
            result = future.result(timeout=30)
            if result['success']:
                if service == 'piot':
                    db.update_service_status(server_id, service, 'ready', result.get('version'), None, result.get('license_until'))
                else:
                    db.update_service_status(server_id, service, 'ready', result.get('version'), None)
            else:
                db.update_service_status(server_id, service, 'error', None, result.get('error'))
            
            if server_id not in results_dict:
                results_dict[server_id] = {'id': server_id, 'services': {}}
            results_dict[server_id]['services'][service] = {
                'success': result['success'],
                'status': result.get('status', 'error'),
                'version': result.get('version'),
                'license_until': result.get('license_until') if service == 'piot' else None,
                'error': result.get('error')
            }
        except Exception as e:
            db.update_service_status(server_id, service, 'error', None, str(e))
            if server_id not in results_dict:
                results_dict[server_id] = {'id': server_id, 'services': {}}
            results_dict[server_id]['services'][service] = {
                'success': False,
                'status': 'error',
                'error': str(e)
            }
    
    return jsonify(list(results_dict.values()))

@app.route('/api/servers/<int:server_id>/status/<service>', methods=['POST'])
def check_service_status(server_id, service):
    server = db.get_server(server_id)
    
    if not server:
        return jsonify({'error': 'Server not found'}), 404
    
    result = check_single_service(server, service)
    
    if result['success']:
        if service == 'piot':
            db.update_service_status(server_id, service, 'ready', result.get('version'), None, result.get('license_until'))
            return jsonify({
                'success': True,
                'status': 'ready',
                'version': result.get('version'),
                'license_until': result.get('license_until')
            })
        else:
            db.update_service_status(server_id, service, 'ready', result.get('version'), None)
            return jsonify({
                'success': True,
                'status': 'ready',
                'version': result.get('version')
            })
    else:
        db.update_service_status(server_id, service, 'error', None, result.get('error'))
        return jsonify({'success': False, 'status': 'error', 'error': result.get('error')}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    try:
        stats = db.get_stats()
        return jsonify(stats)
    except Exception as e:
        print(f"Error getting stats: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/servers/import', methods=['POST'])
def import_servers():
    data = request.json
    if isinstance(data, list):
        count = db.import_from_json(data)
        return jsonify({'success': True, 'imported': count, 'message': f'Импортировано {count} серверов'})
    return jsonify({'success': False, 'message': 'Invalid data format'}), 400

if __name__ == '__main__':
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    app.run(host=host, port=port, debug=debug, threaded=True)