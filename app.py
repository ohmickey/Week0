from flask import Flask,render_template, url_for, jsonify, request, g, make_response, flash, session
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import redirect
from forms import UserCreateForm, UserLoginForm
import random

from bson.objectid import ObjectId

# jwt
from flask_jwt_extended import *
from flask_jwt_extended import JWTManager

# time
import datetime
now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


app = Flask(__name__)
client = MongoClient('localhost', 27017)
db = client.Week0

app.secret_key = 'dev'
app.config['JWT_SECRET_KEY'] = "super-secret"
jwt = JWTManager(app)



@app.route('/', methods=['GET', 'POST'])
def login():
    form = UserLoginForm()
    if g.user is not None:
        return redirect(url_for('board'))

    if request.method =="POST" and form.validate_on_submit():
        error = None
        user_id = form.user_id.data
        user_pw = form.password.data
        
        user = db.users.find_one({'user_id' : user_id})
        if user is None:
            error = "존재하지 않는 아이디 입니다."
        elif not check_password_hash(user['password'], user_pw):
            error = "틀린 비밀번호 입니다."
        if error is None:
            # Authorization 
            session.clear()
            session['user_id'] = user_id
            return redirect(url_for('board'))
        flash(error)
    return render_template('login.html', form = form)


@app.route('/board', methods = ['GET', 'POST'])
def board():
    data = list(db.post.find({}))

    if request.method == 'POST':
        id_receive = request.form['id_give']
        comment_receive = request.form['comment_give']
        nickname = g.nickname
        db.post.update_one({'_id':ObjectId(id_receive)},
            {'$push':{'comment': {'nickname':nickname,'comment_text':comment_receive}}}
        )

        return jsonify({'result':'success'})
    return render_template('board.html', post_list = data)


@app.route('/board_create', methods=['GET', 'POST'])
def board_create():
    if request.method == 'POST':
        nickname = g.nickname
        user_id = g.user
        title_receive = request.form['title_give']
        text_receive = request.form['text_give']
        doc = {
            'title' : title_receive,
            'text' : text_receive,
            'nickname' : nickname,
            'user_id' : user_id,
            'posted_date' : now,
            'comment' : [
            ]
        }
        db.post.insert_one(doc)
        return jsonify({'result':'success'})
    return render_template('board_create.html')




@app.route('/signup', methods=['POST', 'GET'])
def signup():
    form = UserCreateForm()
    if request.method == 'POST' and form.validate_on_submit():
        user_id = form.user_id.data
        created_user_id = db.users.find_one({"user_id" : user_id})
        if not created_user_id:
            username = form.username.data
            nickname = form.nickname.data
            password = generate_password_hash(form.password1.data) 
            email = form.email.data
            
            user_data = {
                'username' : username,
                'user_id' : user_id,
                'nickname' : nickname,
                'password' : password,
                'email' : email,
                'admin' : 0
            }
            db.users.insert_one(user_data)
            return redirect(url_for('login'))
        else:
            flash('이미 존재하는 아이디입니다.')


    return render_template('signup.html', form = form)



@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        user = db.users.find_one({"user_id" : user_id}) 
        id_ = user['user_id']
        nickname_ = user['nickname'] 
        admin_ = user['admin']
        g.user = id_
        g.nickname = nickname_
        g.admin = admin_
    


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/match')
def matching():
    # TODO
    # g.state에 따라 다르게 변하게 하기
    db.matching.drop()
    users = list(db.users.find({"admin" : 0}))
    temp = list()
    for user in users:
        temp.append(user['user_id'])
    random.shuffle(temp)
    for i in range(0, len(temp)-1):
        temp_json = {"from" : temp[i], "to" :temp[i+1], "mission" : "not yet" }
        db.matching.insert_one(temp_json)
    db.matching.insert_one({"from" : temp[len(temp)-1], "to" : temp[0],  "mission" : "not yet"})
    return redirect(url_for('admin'))



@app.route('/admin')
def admin():
    if g.admin == 1:
        user_list = list(db.users.find({"admin" : 0}, {"_id" : 0, "username" : 1, "user_id" : 1, "nickname" : 1}))
        match_list = list(db.matching.find({}, {"_id" : 0 }))
        mission_list = list(db.mission_list.find({}, {"_id": 0}))
        state = list(db.state.find({}))[0]['state']
        return render_template("admin.html", user_list = user_list, match_list = match_list, mission_list = mission_list, state = state)
    else:
        return "관리자만 들어올 수 있습니다."

@app.route('/mission_register', methods=['POST'])
def mission_register():
    mission = request.form['text']
    db.mission_list.insert_one({"mission" : mission})
    return redirect(url_for('admin'))


@app.route('/mission_link')
def mission_link():
    mission_list = list(db.mission_list.find({}, {"_id": 0}))
    length = len(mission_list)
    rand_num = random.randrange(0, length)
    selected_mission = mission_list[rand_num]['mission']

    db.matching.update({"mission" : "not yet"}, {"$set" : {"mission" : selected_mission}})
    return redirect((url_for('admin')))

@app.route('/matching_mission_clear')
def matching_mission_clear():
    db.matching.update_many({}, {"$set" : {"mission" : "not yet"}})
    return redirect((url_for('admin')))




# state = 0 은 준비 상태
# state = 1 게임 중 상태
@app.route('/game', methods=['GET'])
def game():
    state = db.state.find_one({})['state']
    if state == 0: # 게임 준비 -> 게임 시작
        db.state.update({},{"$set" : {"state" : 1}})
        return redirect((url_for('admin')))
    elif state == 1:
        db.state.update({},{"$set" : {"state" : 2}})
        return redirect((url_for('admin')))
    elif state == 2:
        db.state.update({},{"$set" : {"state" : 0}})
        return redirect((url_for('admin')))


@app.route('/manitto', methods=['GET'])
def manitto():
    state = db.state.find_one({})['state']
    if g.user is None:
        return "로그인이 필요합니다."

    if state == 0:
        return render_template('manitto.html', state = state)
    elif state == 1:
        user_id = g.user
        match = db.matching.find_one({"from" : user_id}, {"_id" : 0})
        to = match['to']
        mission = match['mission']
        to = db.users.find_one({"user_id" : to})['username']

        data = {"to" : to, "mission" : mission}
        return render_template('manitto.html', data = data, state = state)
    elif state ==2:
        user_id = g.user
        match = db.matching.find_one({"to" : user_id}, {"_id" : 0})
        your_manitto = match['from']
        manitto_mission = match['mission']
        your_manitto = db.users.find_one({"user_id" : your_manitto})['username']
        print(manitto_mission)
        data = {
            "your_manitto" : your_manitto,
            "manitto_mission" : manitto_mission
        }

        return render_template('manitto.html', data = data, state = state)

@app.route('/delete_board/<post_id>', methods=['GET'])
def delete_board(post_id):
    db.post.delete_one({"_id" : ObjectId(post_id)})
    return redirect(url_for('board'))


@app.route('/modify_board/<string:post_id>', methods=['GET', 'POST'])
def modify_board(post_id):
    if request.method == "POST":
        title_receive = request.form['title_give']
        text_receive = request.form['text_give']
        db.post.update_one({
        "_id" : ObjectId(post_id)}, 
        { "$set" : 
            {   
                'title' : title_receive,
                'text' : text_receive
            }
            }
        )
        return jsonify({'result':'success'})

    contents = db.post.find_one({"_id" : ObjectId(post_id)})

    return render_template('board_create.html', post_id = post_id, contents = contents)

    

if __name__ == '__main__':
    app.run('0.0.0.0', port = 5000, debug = True)