from flask import Flask, jsonify, render_template, request, redirect, url_for

import storage
from config import APP_HOST, APP_PORT, SECRET_KEY
from plate_engine import recognize, status as model_status

app = Flask(__name__)
app.secret_key = SECRET_KEY


@app.before_request
def init():
    storage.setup()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/scan', methods=['GET', 'POST'])
def scan():
    result = None
    if request.method == 'POST':
        result = recognize(
            request.files.get('image'),
            request.form.get('plate'),
            request.form.get('plate_color'),
        )
        if result.get('plate'):
            storage.save_event({
                'plate': result['plate'],
                'gate_role': request.form.get('gate_role') or 'entry',
                'source': 'scan',
                'plate_color': result.get('plate_color'),
                'score': result.get('confidence'),
                'image_path': result.get('image_path'),
                'crop_path': result.get('crop_path'),
                'note': request.form.get('note'),
            })
    return render_template('scan.html', result=result)


@app.route('/manual-entry', methods=['GET', 'POST'])
def manual_entry():
    if request.method == 'POST':
        storage.save_event(request.form)
        return redirect(url_for('logs'))
    return render_template('manual_entry.html')


@app.route('/mobile-entry', methods=['GET', 'POST'])
def mobile_entry():
    if request.method == 'POST':
        data = dict(request.form)
        data['source'] = 'mobile'
        storage.save_event(data)
        return redirect(url_for('logs'))
    return render_template('mobile_entry.html')


@app.route('/vehicles', methods=['GET', 'POST'])
def vehicles():
    if request.method == 'POST':
        storage.save_vehicle(request.form)
        return redirect(url_for('vehicles'))
    return render_template('vehicles.html', vehicles=storage.vehicles())


@app.route('/cameras', methods=['GET', 'POST'])
def cameras():
    if request.method == 'POST':
        storage.save_camera(request.form)
        return redirect(url_for('cameras'))
    return render_template('cameras.html', cameras=storage.cameras())


@app.route('/logs')
def logs():
    return render_template('logs.html', rows=storage.events(100))


@app.route('/status')
def status():
    return jsonify(model_status())


@app.route('/api/dashboard-stats')
def api_dashboard_stats():
    return jsonify(storage.stats())


if __name__ == '__main__':
    storage.setup()
    app.run(host=APP_HOST, port=APP_PORT)
