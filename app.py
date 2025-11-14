from flask import Flask, send_from_directory, request, jsonify
from database import Database
from agent import KousuAgent
import os
from datetime import datetime

app = Flask(__name__)
db = Database()
agent = KousuAgent(db)

@app.route('/')
def index():
    # staticフォルダからindex.htmlを配信
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    return send_from_directory(static_dir, 'index.html')

@app.route('/api/projects', methods=['GET', 'POST'])
def projects():
    if request.method == 'GET':
        projects = db.get_all_projects()
        return jsonify(projects)

    elif request.method == 'POST':
        data = request.json
        project_id = db.add_project(
            name=data.get('name'),
            client=data.get('client', ''),
            description=data.get('description', '')
        )
        return jsonify({'success': True, 'project_id': project_id})

@app.route('/api/members', methods=['GET', 'POST'])
def members():
    if request.method == 'GET':
        members = db.get_all_members()
        return jsonify(members)

    elif request.method == 'POST':
        data = request.json
        member_id = db.add_member(
            name=data.get('name'),
            email=data.get('email', '')
        )
        return jsonify({'success': True, 'member_id': member_id})

@app.route('/api/kousu', methods=['POST'])
def add_kousu():
    data = request.json
    member_id = data.get('member_id')
    if member_id == '':
        member_id = None
    elif member_id:
        member_id = int(member_id)

    success = db.add_or_update_kousu(
        project_id=data.get('project_id'),
        year=data.get('year'),
        month=data.get('month'),
        estimated_hours=float(data.get('estimated_hours', 0)),
        planned_hours=float(data.get('planned_hours', 0)),
        actual_hours=float(data.get('actual_hours', 0)),
        notes=data.get('notes', ''),
        member_id=member_id
    )
    return jsonify({'success': success})

@app.route('/api/kousu/list', methods=['GET'])
def list_kousu():
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    records = db.get_kousu_by_period(year, month)
    return jsonify(records)

@app.route('/api/kousu/by-project', methods=['GET'])
def kousu_by_project():
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    records = db.get_kousu_by_project(year, month)
    return jsonify(records)

@app.route('/api/kousu/by-member', methods=['GET'])
def kousu_by_member():
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    records = db.get_kousu_by_member(year, month)
    return jsonify(records)

@app.route('/api/kousu/summary', methods=['GET'])
def kousu_summary():
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    summary = db.get_summary_by_period(year, month)
    return jsonify(summary)

@app.route('/api/periods', methods=['GET'])
def get_periods():
    periods = db.get_all_years_months()
    return jsonify(periods)

@app.route('/api/agent/chat', methods=['POST'])
def agent_chat():
    try:
        print("[DEBUG] Agent chat endpoint called")
        data = request.json
        print(f"[DEBUG] Request data: {data}")
        message = data.get('message', '')
        year = data.get('year')
        month = data.get('month')

        print(f"[DEBUG] Calling agent.chat with message: {message}, year: {year}, month: {month}")
        response = agent.chat(message, year, month)
        print(f"[DEBUG] Agent response length: {len(response) if response else 0}")
        print(f"[DEBUG] Agent response preview: {response[:100] if response else 'None'}")

        return jsonify({'response': response})
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"[ERROR] Exception in agent_chat: {error_details}")
        return jsonify({'response': f'エラーが発生しました: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
