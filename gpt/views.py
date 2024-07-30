from flask import render_template, request, session, redirect, url_for, flash, jsonify
from flask_socketio import emit
from openai import OpenAI
import random
import string
from datetime import datetime

from . import app, socketio, db
from .models import Users, Chat, Conversation, SurveyResponse, Demographics, BretResponses, CompetitionEntry
from .forms import MultipleChoiceForm, ScaleForm, AttitudeForm, ControlForm, DemographicsForm, LikertScaleForm


# importing openai API
openai_client = OpenAI(
    api_key=app.config['OPENAI_API_KEY']
)
app.secret_key = app.config['SECRET_KEY']
conversation_history = []


# function to generate unique for each participant
def generate_random_code():
    characters = string.digits + string.ascii_uppercase
    return ''.join(random.choice(characters) for _ in range(10))


# route for the welcome page
@app.route("/", methods=["GET", "POST"])
def login():
    if session.get('authenticated'):
        return redirect(url_for('intro'))

    if request.method == 'POST':
        access_code = generate_random_code()
        user = Users.query.filter_by(id=access_code).first()
        if user:
            access_code = generate_random_code()

        # setting the session variables
        session['access_code'] = access_code
        session['authenticated'] = True
        session['total_money'] = 0

        treatment_gpt = random.randint(1, 2)
        session['treatment_gpt'] = treatment_gpt

        # creating entry for user in db
        user = Users(
            id=access_code,
            treatment_gpt=treatment_gpt,
        )
        db.session.add(user)
        db.session.commit()

        if session['treatment_gpt'] == 2:  # creating first chat for user
            new_user_chat = Chat(user_id=user.id)
            db.session.add(new_user_chat)
            db.session.commit()
            return redirect(url_for("chat", chat_id=new_user_chat.id))
        else:
            return redirect(url_for("intro"))

    return render_template("welcome.html")


# route for logout
@app.route("/logout", methods=["GET", "POST"])
def logout():
    session['authenticated'] = False
    if 'access_code' in session:
        session.pop('access_code')
    if 'treatment_gpt' in session:
        session.pop('treatment_gpt')
    return redirect('/')


# route for chat
@app.route("/chat/<int:chat_id>", methods=["GET", "POST"])
def chat(chat_id):
    if not session.get('authenticated'):
        flash('You are not authenticated...', 'warning')
        return redirect(url_for('login'))

    current_chat = Chat.query.filter_by(id=chat_id).first()
    user = Users.query.filter_by(id=session['access_code']).first()

    if not current_chat:  # if by chance there is not a current_chat a new one is created in the db
        return redirect(url_for("new_chat"))

    if current_chat.user_id != user.id:  # if somebody tries to enter a chat that doesn't belong to them they get kicked
        return redirect(url_for("new_chat"))

    return render_template("chatbot.html", current_chat=current_chat)


# route for creating new chat
@app.route("/new_chat", methods=["GET", "POST"])
def new_chat():
    if not session.get('authenticated'):
        flash('You are not authenticated...', 'warning')
        return redirect(url_for('login'))

    user = Users.query.filter_by(id=session['access_code']).first()
    new_user_chat = Chat(user_id=user.id)
    db.session.add(new_user_chat)
    db.session.commit()
    return redirect(url_for('chat', chat_id=new_user_chat.id))


# function to call the api
def generate_long_text(messages, system_message):
    persona = [{'role': 'system', 'content': system_message}]

    result = openai_client.chat.completions.create(
        model=app.config["OPENAI_MODEL"],
        messages=persona + messages,
        temperature=0.5,
        stream=True,
        max_tokens=1000
    )
    return result


# socket for handling messages
@socketio.on('chat_message')
def handle_message(data):
    message = data['message']
    chat_id = data['chat_id']

    new_conversation = Conversation(chat_id=chat_id, message=message, role="user")
    db.session.add(new_conversation)
    db.session.commit()

    chat_conversation = Conversation.query.filter_by(chat_id=chat_id).all()

    chat = Chat.query.filter_by(id=chat_id).first()
    system_message = chat.system_message
    if not system_message:
        system_message = ""

    conversation_history = []
    for row in chat_conversation:
        conversation_history += [{"role": row.role, "content": row.message}]

    response = generate_long_text(conversation_history, system_message)

    bot_response = ""
    for chunk in response:
        try:
            chunk_text = chunk.choices[0].delta.content
            bot_response += chunk_text
            emit('stream_response', {'message': chunk_text})
        except Exception as e:
            print(e)
            break

    new_conversation = Conversation(chat_id=chat_id, message=bot_response, role="assistant")
    db.session.add(new_conversation)
    db.session.commit()


# route for introduction page
@app.route("/introduction", methods=["GET", "POST"])
def intro():
    if not session.get('authenticated'):
        flash('You are not authenticated...', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        return redirect(url_for("trial", trial_n=1))

    return render_template("introduction.html")


# route for trial page: trial_n =1 is instructions, trial_n=2 is trials
@app.route("/trial/<int:trial_n>", methods=["GET", "POST"])
def trial(trial_n):
    if not session.get('authenticated'):
        flash('You are not authenticated...', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        if trial_n == 1:
            return redirect(url_for('trial', trial_n=2))
        else:
            return redirect(url_for("bret_game", task_number=1))

    return render_template("trial.html", trial_n=trial_n)


# route for real bret task: task_number=1 and 3 is intructions, task_number=2 and 4 are the experiments
@app.route("/bret_game/<int:task_number>", methods=["GET", "POST"])
def bret_game(task_number):
    if not session.get('authenticated'):
        flash('You are not authenticated...', 'warning')
        return redirect(url_for('login'))

    user = Users.query.filter_by(id=session['access_code']).first()

    if task_number > 4:
        return redirect(url_for('total_money'))

    if request.method == 'POST':
        return redirect(url_for('bret_game', task_number=task_number + 1))

    if user.treatment_gpt == 2:
        with open('./system_message.txt', 'r') as file:
            system_message = file.read().strip()

        if task_number == 1:
            current_chat = Chat(user_id=user.id, task_number=task_number, system_message=system_message)
            db.session.add(current_chat)
            db.session.commit()
        else:
            current_chat = Chat.query.filter_by(user_id=session['access_code'], task_number=1).first()

        chat_conversation = Conversation.query.filter_by(chat_id=current_chat.id).all()

    else:
        current_chat = None
        chat_conversation = None

    return render_template("bret_game.html", chat_conversation=chat_conversation, current_chat=current_chat,
                           total_money=session['total_money'], task_number=task_number)


@app.route('/api/reveal', methods=['POST'])
def reveal():
    if not session.get('authenticated'):
        return jsonify({'error': 'Not authenticated'}), 401

    selected_cards = request.json['selected_cards']
    task_number = request.json['task_number']
    is_trial = request.json['is_trial']
    bomb_index = random.randint(0, 63)

    if bomb_index in selected_cards:
        score = 0  # If the bomb is in the selected cards, the score is 0
    else:
        score = sum(0.20 for i in range(64) if i in selected_cards and i != bomb_index)  # Calculate the score normally
        score = round(score, 2)

    user = Users.query.filter_by(id=session['access_code']).first()

    existing_entry = BretResponses.query.filter_by(user_id=user.id, task_number=task_number, is_trial=is_trial).first()

    if existing_entry:
        return jsonify({
            'error': 'Entry already exists',
            'next_task': task_number + 1
        }), 409

    bret_response = BretResponses(
        user_id=user.id,
        task_number=task_number,
        is_trial=is_trial,
        n_cards=len(selected_cards),
        final_pay=score
    )
    db.session.add(bret_response)
    db.session.commit()

    # update the total_money variable if the score doesnt come from a trial round
    if not is_trial:
        session['total_money'] += round(score, 2)

    return jsonify({
        'bomb_index': bomb_index,
        'score': score
    })


@app.route("/total_money", methods=['GET', 'POST'])
def total_money():
    if not session.get('authenticated'):
        flash('You are not authenticated...', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        return redirect(url_for('trust', question_n=1))
    return render_template('total_money.html', total_money=session['total_money'])


@app.route("/001/<int:question_n>", methods=['GET', 'POST'])
def trust(question_n):
    if not session.get('authenticated'):
        flash('You are not authenticated...', 'warning')
        return redirect(url_for('login'))

    user = Users.query.filter_by(id=session['access_code']).first()

    if user.treatment_gpt == 1:
        return redirect(url_for('control'))

    questions = [
        "Using the AI improves my task performance.",
        "Using the AI in my task increases my productivity.",
        "Using the AI enhances my effectiveness in my task.",
        "I find the AI to be useful in my task.",
        "The decision to bet was due to the AI's evaluation.",
        "The decision to bet was due to my action.",
        "The decision to bet was due to something other than the AI's or my actions.",
        "The AI took responsibility for its actions.",
        "The AI always provides the advice I require to make my decision.",
        "The AI performs reliably.",
        "The AI responds the same way under the same conditions at different times.",
        "I can rely on the AI to function properly.",
        "The AI analyzes problems consistently.",
        "My typical approach is to trust new information technologies until they prove to me that I shouldn’t.",
        "I usually trust in information technology until it gives me a reason not to.",
        "I generally give an information technology the benefit of the doubt when I first use it."
    ]

    if question_n > len(questions):
        return redirect(url_for('loc', scale_number=1))

    current_question = questions[question_n - 1]
    form = LikertScaleForm()

    if request.method == 'POST' and form.validate():
        answer = form.question.data

        # Save the response
        response = SurveyResponse(
            user_id=user.id,
            scale="trust",
            task_number=question_n,
            question=current_question,
            answer=answer
        )
        db.session.add(response)
        db.session.commit()

        # Redirect to the next scale
        return redirect(url_for('trust', question_n=question_n + 1))

    return render_template('trust.html', current_question=current_question, form=form, question_n=question_n)


@app.route("/loc/<int:scale_number>", methods=['GET', 'POST'])
def loc(scale_number):
    if not session.get('authenticated'):
        flash('You are not authenticated...', 'warning')
        return redirect(url_for('login'))

    user = Users.query.filter_by(id=session['access_code']).first()

    if user.treatment_gpt == 1:
        return redirect(url_for('control'))

    scales = [
        {
            'type': 'scale',
            'question': "I'm my own boss.",
            'form': ScaleForm,
            'choices': [('1', '1. Does not apply at all'), ('2', '2. Applies a bit'),
                        ('3', '3. Applies somewhat'), ('4', '4. Applies mostly'), ('5', '5. Applies completely')]
        },
        {
            'type': 'scale',
            'question': "If I work hard, I will succeed",
            'form': ScaleForm,
            'choices': [('1', '1. Does not apply at all'), ('2', '2. Applies a bit'),
                        ('3', '3. Applies somewhat'), ('4', '4. Applies mostly'), ('5', '5. Applies completely')]
        },
        {
            'type': 'scale',
            'question': "Whether at work or in my private life: What I do is mainly determined by others.",
            'form': ScaleForm,
            'choices': [('1', '1. Does not apply at all'), ('2', '2. Applies a bit'),
                        ('3', '3. Applies somewhat'), ('4', '4. Applies mostly'), ('5', '5. Applies completely')]
        },
        {
            'type': 'scale',
            'question': "Fate often gets in the way of my plans.",
            'form': ScaleForm,
            'choices': [('1', '1. Does not apply at all'), ('2', '2. Applies a bit'),
                        ('3', '3. Applies somewhat'), ('4', '4. Applies mostly'), ('5', '5. Applies completely')]
        }
    ]

    if scale_number > len(scales):
        return redirect(url_for('control'))

    current_scale = scales[scale_number - 1]
    form = current_scale['form'](choices=current_scale['choices'])

    if request.method == 'POST' and form.validate():
        answer = form.question.data

        # Save the response
        response = SurveyResponse(
            user_id=user.id,
            scale="locus_control",
            task_number=scale_number,
            question=current_scale['question'],
            answer=answer
        )
        db.session.add(response)
        db.session.commit()

        # Redirect to the next scale
        return redirect(url_for('loc', scale_number=scale_number + 1))

    return render_template('loc.html', scale=current_scale, form=form, scale_number=scale_number)


@app.route("/attitudes/<int:question_number>", methods=['GET', 'POST'])
def attitude(question_number):
    if not session.get('authenticated'):
        flash('You are not authenticated...', 'warning')
        return redirect(url_for('login'))

    user = Users.query.filter_by(id=session['access_code']).first()

    questions = [
        "I believe that AI will improve my life.",
        "I believe that AI will improve my work.",
        "I think I will use AI technology in the future.",
        "I think AI technology is positive for humanity."
    ]

    if question_number > len(questions):
        return redirect(url_for('control'))  # Redirect to a thank you page when all questions are completed

    current_question = questions[question_number - 1]
    form = AttitudeForm()

    if request.method == 'POST' and form.validate():
        answer = form.slider.data

        # Save the response
        response = SurveyResponse(
            user_id=user.id,
            scale="attitudes",
            task_number=question_number,
            question=current_question,
            answer=answer
        )
        db.session.add(response)
        db.session.commit()

        # Redirect to the next question
        return redirect(url_for('attitude', question_number=question_number + 1))

    form.slider.label.text = current_question

    return render_template('attitudes.html', form=form, question_number=question_number)


@app.route("/control", methods=['GET', 'POST'])
def control():
    if not session.get('authenticated'):
        flash('You are not authenticated...', 'warning')
        return redirect(url_for('login'))

    user = Users.query.filter_by(id=session['access_code']).first()

    questions = [
        "I do not feel comfortable about taking chances.",
        "I prefer situations that have foreseeable outcomes.",
        "Before I make a decision, I like to be absolutely sure how things will turn out.",
        "I avoid situations that have uncertain outcomes.",
        "I feel comfortable improvising in new situations.",
        "I feel nervous when I have to make decisions in uncertain situations."
    ]

    form = ControlForm()

    if request.method == 'POST' and form.validate_on_submit():
        for i, (question, answer) in enumerate(zip(questions, form.answers.data)):
            survey_response = SurveyResponse(
                user_id=user.id,
                scale="general_risk_aversion",
                task_number=i + 1,
                question=question,
                answer=str(answer)
            )
            db.session.add(survey_response)

        db.session.commit()
        return redirect(url_for('demographic'))

    enumerated_questions = list(enumerate(questions, start=1))

    return render_template('control.html', form=form, questions=questions, enumerated_questions=enumerated_questions)


@app.route("/demographic", methods=['GET', 'POST'])
def demographic():
    if not session.get('authenticated'):
        flash('You are not authenticated...', 'warning')
        return redirect(url_for('login'))

    user = Users.query.filter_by(id=session['access_code']).first()

    form = DemographicsForm()

    if form.validate_on_submit():
        demographics = Demographics(
            user_id=user.id,
            age=form.age.data,
            gender=form.gender.data,
            education=form.education.data,
            profession=form.profession.data,
            country=form.country.data
        )
        db.session.add(demographics)
        db.session.commit()
        return redirect(url_for('final'))  # Redirect to a thank you page

    return render_template('demographics.html', form=form)


@app.route("/final", methods=['GET', 'POST'])
def final():
    if not session.get('authenticated'):
        flash('You are not authenticated...', 'warning')
        return redirect(url_for('login'))

    user = Users.query.filter_by(id=session['access_code']).first()
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('login'))

    total_money = session["total_money"]

    user.finished = True
    user.finished_at = datetime.now()
    db.session.commit()

    if request.method == 'POST':
        # Handle competition entry form submission
        email = request.form.get('email')
        amount_collected = total_money

        # Validate email (basic validation)
        if not email or '@' not in email:
            flash('Please enter a valid email address.', 'error')
            return redirect(url_for('final'))

        # Check if email already exists in competition entries
        existing_entry = CompetitionEntry.query.filter_by(email=email).first()
        if existing_entry:
            flash('This email has already been entered into the competition.', 'error')
            return redirect(url_for('final'))

        # Create new competition entry
        new_entry = CompetitionEntry(email=email, amount_collected=amount_collected)
        db.session.add(new_entry)
        db.session.commit()

        flash('You have successfully entered the competition. '
              'We will notify you by email in case you win the raffle.', 'success')
        return redirect(url_for('logout'))  # Redirect to your home or index page after successful entry

    return render_template("final.html", user=user, total_money=total_money)
