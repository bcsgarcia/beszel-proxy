from flask import Flask, jsonify, Response
import requests
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)

# Configurações do Beszel
BESZEL_URL = os.getenv('BESZEL_URL', 'http://192.168.1.249:8090')
BESZEL_EMAIL = os.getenv('BESZEL_EMAIL')
BESZEL_PASSWORD = os.getenv('BESZEL_PASSWORD')
REDIRECT_URL = os.getenv('REDIRECT_URL', BESZEL_URL)

# Opções de exibição (configuráveis via .env)
HIDE_KERNEL = os.getenv('HIDE_KERNEL', 'false').lower() == 'true'
HIDE_UPTIME = os.getenv('HIDE_UPTIME', 'false').lower() == 'true'
HIDE_CPU_INFO = os.getenv('HIDE_CPU_INFO', 'false').lower() == 'true'
HIDE_IP = os.getenv('HIDE_IP', 'false').lower() == 'true'
OPEN_IN_NEW_TAB = os.getenv('OPEN_IN_NEW_TAB', 'false').lower() == 'true'

# Auto-reload (em segundos)
RELOAD_INTERVAL = int(os.getenv('RELOAD_INTERVAL', '3'))

# Cache do token
token_cache = {
    'token': None,
    'expires_at': None
}

def get_auth_token():
    """
    Obtém o token de autenticação do Beszel.
    Usa cache se o token ainda for válido.
    """
    now = datetime.now()
    
    # Verifica se temos um token válido em cache
    if token_cache['token'] and token_cache['expires_at']:
        if now < token_cache['expires_at']:
            logger.info("Usando token do cache")
            return token_cache['token']
    
    # Faz login para obter novo token
    logger.info("Obtendo novo token de autenticação")
    try:
        response = requests.post(
            f"{BESZEL_URL}/api/collections/users/auth-with-password",
            json={
                "identity": BESZEL_EMAIL,
                "password": BESZEL_PASSWORD
            },
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        response.raise_for_status()
        
        data = response.json()
        token = data.get('token')
        
        if not token:
            logger.error("Token não encontrado na resposta")
            return None
        
        # Armazena no cache (expira em 6 horas para segurança)
        token_cache['token'] = token
        token_cache['expires_at'] = now + timedelta(hours=6)
        
        logger.info("Novo token obtido com sucesso")
        return token
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao obter token: {e}")
        return None

def get_systems_data(token):
    """
    Obtém os dados dos sistemas do Beszel.
    """
    try:
        response = requests.get(
            f"{BESZEL_URL}/api/collections/systems/records",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json"
            },
            timeout=10
        )
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro ao obter dados dos sistemas: {e}")
        return None

def format_uptime(uptime_seconds):
    """
    Formata o uptime em dias ou horas.
    """
    if uptime_seconds >= 86400:
        days = uptime_seconds * 0.000011574
        return f"{days:.1f}d"
    else:
        hours = uptime_seconds * 0.000277778
        return f"{hours:.1f}h"

def generate_html(data):
    """
    Gera o HTML completo com os dados dos sistemas e auto-reload.
    """
    items = data.get('items', [])
    
    if not items:
        return '<div style="color: #94a3b8; padding: 1rem;">Nenhum sistema encontrado</div>'
    
    # Adiciona o script de auto-reload no início
    html_parts = ['''
    <div id="beszel-widget">
        <div style="display: flex; flex-direction: column; gap: 1rem;">
    ''']
    
    for item in items:
        info = item.get('info', {})
        name = item.get('name', 'Unknown')
        status = item.get('status', 'unknown')
        host = item.get('host', '')
        
        cpu_percent = info.get('cpu', 0)
        mem_percent = info.get('mp', 0)
        disk_percent = info.get('dp', 0)
        kernel = info.get('k', 'N/A')
        uptime_sec = info.get('u', 0)
        cpu_model = info.get('m', 'N/A').replace('CPU ', '')
        
        # Status indicator
        status_color = '#22c55e' if status == 'up' else '#ef4444'
        
        # Card HTML
        card_html = f'''
        <div style="background: rgba(30, 41, 59, 0.5); border-radius: 0.75rem; padding: 1.25rem; border: 1px solid rgba(71, 85, 105, 0.5);">
            <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem;">
                <span style="color: {status_color}; font-size: 1.5em; line-height: 1;">●</span>
        '''
        
        # Nome/Link do servidor
        if REDIRECT_URL:
            target = ' target="_blank" rel="noopener"' if OPEN_IN_NEW_TAB else ''
            card_html += f'''
                <a href="{REDIRECT_URL}/system/{name}"{target}
                   style="color: #60a5fa; text-decoration: none; font-weight: 600; font-size: 1.25em; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                    {name}
                </a>
            '''
        else:
            card_html += f'''
                <span style="color: #60a5fa; font-weight: 600; font-size: 1.25em; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                    {name}
                </span>
            '''
        
        card_html += '</div>'
        
        # IP/Host
        if not HIDE_IP and host:
            card_html += f'''
            <p style="font-size: 0.95em; color: #94a3b8; margin: 0 0 1rem 0; font-weight: 400;">{host}</p>
            '''
        
        card_html += '<div style="display: flex; flex-direction: column; gap: 0.625rem; font-size: 0.95em;">'
        
        # Kernel
        if not HIDE_KERNEL:
            card_html += f'''
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="color: #94a3b8;">Kernel:</span>
                <span style="font-weight: 500; color: #e2e8f0;">{kernel}</span>
            </div>
            '''
        
        # Uptime
        if not HIDE_UPTIME:
            uptime_formatted = format_uptime(uptime_sec)
            card_html += f'''
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="color: #94a3b8;">Uptime:</span>
                <span style="font-weight: 500; color: #e2e8f0;">{uptime_formatted}</span>
            </div>
            '''
        
        # CPU Info
        if not HIDE_CPU_INFO:
            card_html += f'''
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="color: #94a3b8;">CPU:</span>
                <span style="font-weight: 500; color: #e2e8f0;">{cpu_model}</span>
            </div>
            '''
        
        # Separador
        card_html += '''
        <div style="border-top: 1px solid rgba(71, 85, 105, 0.5); margin: 0.75rem 0;"></div>
        '''
        
        # CPU com barra
        card_html += f'''
        <div style="display: flex; flex-direction: column; gap: 0.375rem;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="color: #e2e8f0;">📊 CPU:</span>
                <span style="font-weight: 700; font-size: 1.05em; color: #e2e8f0;">{cpu_percent:.1f}%</span>
            </div>
            <div style="width: 100%; height: 8px; background: rgba(71, 85, 105, 0.4); border-radius: 4px; overflow: hidden;">
                <div style="height: 100%; background: linear-gradient(90deg, #3b82f6, #60a5fa); width: {cpu_percent:.1f}%; transition: width 0.3s ease;"></div>
            </div>
        </div>
        '''
        
        # Memory com barra
        card_html += f'''
        <div style="display: flex; flex-direction: column; gap: 0.375rem;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="color: #e2e8f0;">🧠 Memory:</span>
                <span style="font-weight: 700; font-size: 1.05em; color: #e2e8f0;">{mem_percent:.1f}%</span>
            </div>
            <div style="width: 100%; height: 8px; background: rgba(71, 85, 105, 0.4); border-radius: 4px; overflow: hidden;">
                <div style="height: 100%; background: linear-gradient(90deg, #8b5cf6, #a78bfa); width: {mem_percent:.1f}%; transition: width 0.3s ease;"></div>
            </div>
        </div>
        '''
        
        # Disk com barra
        card_html += f'''
        <div style="display: flex; flex-direction: column; gap: 0.375rem;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="color: #e2e8f0;">💾 Disk:</span>
                <span style="font-weight: 700; font-size: 1.05em; color: #e2e8f0;">{disk_percent:.1f}%</span>
            </div>
            <div style="width: 100%; height: 8px; background: rgba(71, 85, 105, 0.4); border-radius: 4px; overflow: hidden;">
                <div style="height: 100%; background: linear-gradient(90deg, #10b981, #34d399); width: {disk_percent:.1f}%; transition: width 0.3s ease;"></div>
            </div>
        </div>
        '''
        
        card_html += '</div></div>'
        html_parts.append(card_html)
    
    # Fecha o container e adiciona o script de auto-reload
    html_parts.append(f'''
        </div>
    </div>
    <script>
        (function() {{
            // Auto-reload a cada {RELOAD_INTERVAL} segundos
            setInterval(function() {{
                fetch(window.location.href)
                    .then(response => response.text())
                    .then(html => {{
                        const parser = new DOMParser();
                        const doc = parser.parseFromString(html, 'text/html');
                        const newContent = doc.getElementById('beszel-widget');
                        const currentContent = document.getElementById('beszel-widget');
                        
                        if (newContent && currentContent) {{
                            currentContent.innerHTML = newContent.innerHTML;
                        }}
                    }})
                    .catch(error => console.error('Erro ao recarregar:', error));
            }}, {RELOAD_INTERVAL * 1000});
        }})();
    </script>
    ''')
    
    return ''.join(html_parts)

@app.route('/api/systems', methods=['GET'])
def get_systems():
    """
    Endpoint que retorna os dados brutos em JSON.
    """
    token = get_auth_token()
    if not token:
        return jsonify({
            "error": "Falha ao obter token de autenticação"
        }), 500
    
    data = get_systems_data(token)
    if data is None:
        return jsonify({
            "error": "Falha ao obter dados dos sistemas"
        }), 500
    
    return jsonify(data)

@app.route('/widget', methods=['GET'])
def get_widget_json():
    """
    Endpoint que retorna JSON com HTML embutido.
    """
    token = get_auth_token()
    if not token:
        error_html = '<div style="color: #ef4444; padding: 1rem; background: rgba(239, 68, 68, 0.1); border-radius: 0.5rem; border: 1px solid #ef4444;">❌ Erro ao autenticar no Beszel</div>'
        return jsonify({"html": error_html}), 500
    
    data = get_systems_data(token)
    if data is None:
        error_html = '<div style="color: #ef4444; padding: 1rem; background: rgba(239, 68, 68, 0.1); border-radius: 0.5rem; border: 1px solid #ef4444;">❌ Erro ao obter dados dos sistemas</div>'
        return jsonify({"html": error_html}), 500
    
    html = generate_html(data)
    return jsonify({
        "html": html,
        "timestamp": datetime.now().isoformat(),
        "systems_count": len(data.get('items', []))
    })

@app.route('/widget-html', methods=['GET'])
@app.route('/', methods=['GET'])
def get_widget_html():
    """
    Endpoint que retorna HTML puro (não JSON).
    """
    token = get_auth_token()
    if not token:
        error_html = '<div style="color: #ef4444; padding: 1rem; background: rgba(239, 68, 68, 0.1); border-radius: 0.5rem; border: 1px solid #ef4444;">❌ Erro ao autenticar no Beszel</div>'
        return Response(error_html, mimetype='text/html'), 500
    
    data = get_systems_data(token)
    if data is None:
        error_html = '<div style="color: #ef4444; padding: 1rem; background: rgba(239, 68, 68, 0.1); border-radius: 0.5rem; border: 1px solid #ef4444;">❌ Erro ao obter dados dos sistemas</div>'
        return Response(error_html, mimetype='text/html'), 500
    
    html = generate_html(data)
    return Response(html, mimetype='text/html')

@app.route('/health', methods=['GET'])
def health():
    """
    Endpoint de health check.
    """
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "beszel_url": BESZEL_URL,
        "reload_interval": RELOAD_INTERVAL
    })

if __name__ == '__main__':
    if not BESZEL_EMAIL or not BESZEL_PASSWORD:
        logger.error("BESZEL_EMAIL e BESZEL_PASSWORD devem estar configurados no .env")
        exit(1)
    
    logger.info(f"Iniciando Beszel Proxy na porta 8091")
    logger.info(f"Beszel URL: {BESZEL_URL}")
    logger.info(f"Redirect URL: {REDIRECT_URL}")
    logger.info(f"Auto-reload: {RELOAD_INTERVAL} segundos")
    
    app.run(host='0.0.0.0', port=8091, debug=False)
