from flask import render_template, request, redirect, url_for, send_file, Flask
import time
from datetime import datetime
import os

app = Flask(__name__)


# @app.route('/', methods=['GET'])
# def default():
#    return send_file("")
@app.route('/audio/<filename>', methods=['POST', 'GET'])
def serve_audio(filename):
    audio_path = os.path.join("audio_clips", filename)

    response = send_file(audio_path)
    response.headers['Content-Type'] = 'audio/mp3'
    response.headers['Content-Disposition'] = f'inline; filename={filename}'
    return response


@app.route('/add_department', methods=['GET', 'POST'])
def add_department():
    if request.method == 'POST':
        department_id = request.form['department_id']
        tone1 = float(request.form['tone1'])
        tone2 = float(request.form['tone2'])
        user = {
            'name': request.form['name'],
            'email': request.form['email'],
            'phone': request.form['phone']
        }

        with open('db.yml', 'r') as file:
            departments = yaml.load(file, Loader=yaml.FullLoader)

        if not department_id in departments:
            departments[department_id] = {
                'tone1': tone1,
                'tone2': tone2,
                'users': [user]
            }

            with open('db.yml', 'w') as file:
                yaml.dump(departments, file)
        return redirect(url_for('add_department'))

    return render_template('add_department.html')


@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False)
