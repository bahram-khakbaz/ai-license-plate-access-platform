from flask import Flask, jsonify, render_template, request, redirect, url_for, send_file

import storage
from config import APP_HOST, APP_PORT, SECRET_KEY
from import_tools import build_vehicle_template, import_vehicles_excel
from plate_engine import recognize, status as model_status

app = Flask(__name__)
app.secret_key = SECRET_KEY


@app.before_request
def init():
    storage.setup()


@app.route('/')
def index():
    sites = storage.sites(active_only=True)
    return render_template('index.html', sites=sites)


@app.route('/scan', methods=['GET', 'POST'])
def scan():
    result = None
    sites = storage.sites(active_only=True)
    if request.method == 'POST':
        result = recognize(request.files.get('image'), request.form.get('plate'), request.form.get('plate_color'))
        if result.get('plate'):
            storage.save_event({
                'site_id': request.form.get('site_id'),
                'plate': result['plate'],
                'gate_role': request.form.get('gate_role') or 'entry',
                'source': 'scan',
                'plate_color': result.get('plate_color'),
                'score': result.get('confidence'),
                'image_path': result.get('image_path'),
                'crop_path': result.get('crop_path'),
                'note': request.form.get('note'),
            })
    return render_template('scan.html', result=result, sites=sites)


@app.route('/manual-entry', methods=['GET', 'POST'])
def manual_entry():
    sites = storage.sites(active_only=True)
    if request.method == 'POST':
        storage.save_event(request.form)
        return redirect(url_for('logs', site_id=request.form.get('site_id') or ''))
    return render_template('manual_entry.html', sites=sites)


@app.route('/mobile-entry', methods=['GET', 'POST'])
def mobile_entry():
    sites = storage.sites(active_only=True)
    if request.method == 'POST':
        data = dict(request.form)
        data['source'] = 'mobile'
        storage.save_event(data)
        return redirect(url_for('logs', site_id=request.form.get('site_id') or ''))
    return render_template('mobile_entry.html', sites=sites)


@app.route('/vehicles', methods=['GET', 'POST'])
def vehicles():
    sites = storage.sites(active_only=True)
    selected_site_id = request.values.get('site_id') or ''
    if request.method == 'POST':
        storage.save_vehicle(request.form)
        return redirect(url_for('vehicles', site_id=request.form.get('site_id') or ''))
    return render_template('vehicles.html', vehicles=storage.vehicles(selected_site_id or None), sites=sites, selected_site_id=selected_site_id)


@app.route('/vehicles/template.xlsx')
def vehicle_template():
    output = build_vehicle_template()
    return send_file(output, as_attachment=True, download_name='vehicle-import-template.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@app.route('/vehicles/import', methods=['GET', 'POST'])
def vehicle_import():
    result = None
    sites = storage.sites(active_only=True)
    selected_site_id = request.values.get('site_id') or ''
    if request.method == 'POST':
        uploaded = request.files.get('file')
        result = import_vehicles_excel(uploaded, request.form.get('site_id'))
        selected_site_id = request.form.get('site_id') or ''
    return render_template('vehicle_import.html', sites=sites, selected_site_id=selected_site_id, result=result)


@app.route('/cameras', methods=['GET', 'POST'])
def cameras():
    sites = storage.sites(active_only=True)
    selected_site_id = request.values.get('site_id') or ''
    if request.method == 'POST':
        storage.save_camera(request.form)
        return redirect(url_for('cameras', site_id=request.form.get('site_id') or ''))
    return render_template('cameras.html', cameras=storage.cameras(selected_site_id or None), sites=sites, selected_site_id=selected_site_id)


@app.route('/logs')
def logs():
    sites = storage.sites(active_only=True)
    selected_site_id = request.args.get('site_id') or ''
    return render_template('logs.html', rows=storage.events(100, selected_site_id or None), sites=sites, selected_site_id=selected_site_id)


@app.route('/settings/sites', methods=['GET', 'POST'])
def site_settings():
    if request.method == 'POST':
        storage.save_site(request.form)
        return redirect(url_for('site_settings'))
    return render_template('settings_sites.html', sites=storage.sites(active_only=False))


@app.route('/settings/sites/<int:site_id>/toggle', methods=['POST'])
def site_toggle(site_id):
    storage.toggle_site(site_id)
    return redirect(url_for('site_settings'))


@app.route('/status')
def status():
    return jsonify(model_status())


@app.route('/api/dashboard-stats')
def api_dashboard_stats():
    return jsonify(storage.stats(request.args.get('site_id') or None))


@app.route('/api/sites')
def api_sites():
    return jsonify(storage.sites(active_only=True))


if __name__ == '__main__':
    storage.setup()
    app.run(host=APP_HOST, port=APP_PORT)
