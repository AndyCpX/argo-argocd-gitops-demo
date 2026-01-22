import os
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/', methods=['GET'])
def get_env_vars():
    stage = os.environ.get('STAGE', 'not set')
    tenant = os.environ.get('TENANT', 'not set')

    return jsonify({
        'stage': stage,
        'tenant': tenant
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
