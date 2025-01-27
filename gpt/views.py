from flask import render_template, request, session, redirect, url_for, flash, jsonify
from flask_socketio import emit
from openai import OpenAI
import random
import string
from datetime import datetime

from . import app, socketio, db
from .models import Users, Chat, Conversation, SurveyResponse, Demographics, BretResponses, CompetitionEntry
from .forms import MultipleChoiceForm, ScaleForm, AttitudeForm, ControlForm, DemographicsForm, LikertScaleForm, ChoiceForm, AIUsageForm


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
        max_tokens=1000,
        response_format={"type": "text"}
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


@app.route("/ai_familiarity", methods=["GET", "POST"])
def ai_familiarity():
    if not session.get('authenticated'):
        flash('You are not authenticated...', 'warning')
        return redirect(url_for('login'))

    user = Users.query.filter_by(id=session['access_code']).first()
    if user.treatment_gpt == 1:
        return redirect(url_for('intro'))

    question = "How often, if at all, do you use generative AI tools or chatbots for any purpose?"
    form = AIUsageForm()

    if request.method == 'POST' and form.validate_on_submit():
        answer = form.ai_usage_frequency.data
        new_response = SurveyResponse(
            user_id=user.id,
            scale="familiarity",
            task_number=1,
            question=question,
            answer=answer
        )
        db.session.add(new_response)
        db.session.commit()

        return redirect(url_for("intro"))

    return render_template("familiarity.html", form=form)


# route for introduction page
@app.route("/introduction", methods=["GET", "POST"])
def intro():
    if not session.get('authenticated'):
        flash('You are not authenticated...', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        return redirect(url_for("trial", trial_n=1))

    return render_template("introduction.html")


# route for trial page: trial_n=1 is instructions, trial_n=2 is trials
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


# route for real bret task: task_number=1 and 3 are instructions, task_number=2 and 4 are the experiments
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
    confidence = request.json['confidence']
    bomb_index = random.randint(0, 63)

    if bomb_index in selected_cards:
        score = 0  # If the bomb is in the selected cards, the score is 0
    else:
        score = sum(0.20 for i in range(64) if i in selected_cards and i != bomb_index)  # Calculate the score normally
        score = round(score, 2)

    user = Users.query.filter_by(id=session['access_code']).first()

    existing_entry = BretResponses.query.filter_by(user_id=user.id, task_number=task_number, is_trial=is_trial).first()

    if is_trial is False and existing_entry:
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

    if confidence:
        survey_response = SurveyResponse(
            user_id=user.id,
            scale='confidence_scale',
            task_number=task_number,
            question='How confident are you in the decision you just made?',
            answer=confidence
        )
        db.session.add(survey_response)
        db.session.commit()

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
        return redirect(url_for('attention_check'))
    return render_template('total_money.html', total_money=session['total_money'])


@app.route("/attention_check", methods=['GET', 'POST'])
def attention_check():
    if not session.get('authenticated'):
        flash('You are not authenticated...', 'warning')
        return redirect(url_for('login'))

    user = Users.query.filter_by(id=session['access_code']).first()

    if request.method == 'POST':
        answer = request.form.get('attention_answer')
        survey_response = SurveyResponse(
            user_id=user.id,
            scale='attention_check',
            task_number=1,
            question='How many total cards were in the grid?',
            answer=answer
        )
        db.session.add(survey_response)
        db.session.commit()

        return redirect(url_for('pr'))

    return render_template('attention_check.html')


@app.route("/pr", methods=['GET', 'POST'])
def pr():
    if not session.get('authenticated'):
        flash('You are not authenticated...', 'warning')
        return redirect(url_for('login'))

    user = Users.query.filter_by(id=session['access_code']).first()

    if request.method == 'POST':
        for i in range(1, 4):
            answer = request.form.get(f'pr_question_{i}')
            survey_response = SurveyResponse(
                user_id=user.id,
                scale='perceived_responsibility',
                task_number=i,
                question=f'PR Question {i}',
                answer=answer
            )
            db.session.add(survey_response)
        db.session.commit()

        return redirect(url_for('trust'))

    return render_template('pr.html')


@app.route("/trust", methods=['GET', 'POST'])
def trust():
    if not session.get('authenticated'):
        flash('You are not authenticated...', 'warning')
        return redirect(url_for('login'))

    user = Users.query.filter_by(id=session['access_code']).first()

    if user.treatment_gpt == 1:
        return redirect(url_for('locus'))

    questions = [
        "1. I am confident in the AI tool. I feel that it works well.",
        "2. The outputs of the AI tool are very predictable.",
        "3. The AI tool is very reliable. I can count on it to be correct all the time.",
        "4. I feel safe that when I rely on the AI tool, I will get the right answers.",
        "5. I like using the AI tool for decision-making."
    ]

    if request.method == 'POST':
        for i in range(1, 6):
            answer = request.form.get(f'trust_question_{i}')
            survey_response = SurveyResponse(
                user_id=user.id,
                scale='trust_ai',
                task_number=i,
                question=questions[i-1],
                answer=answer
            )
            db.session.add(survey_response)
        db.session.commit()

        return redirect(url_for('locus'))  # Redirect to the next page

    return render_template('trust1.html', questions=questions)


@app.route("/locus", methods=['GET', 'POST'])
def locus():
    if not session.get('authenticated'):
        flash('You are not authenticated...', 'warning')
        return redirect(url_for('login'))

    user = Users.query.filter_by(id=session['access_code']).first()

    questions = [
        "1. When I make plans, I am almost certain that I can make them work.",
        "2. Getting a good job depends mainly on being in the right place at the right time.",
        "3. Getting people to do the right things depends upon ability; luck has nothing to do with it.",
        "4. What happens to me is my own doing.",
        "5. Select Strongly agree in this question so we know you are paying attention.",
        "6. Many of the unhappy things in people's lives are partly due to bad luck.",
        "7. Many times I feel that I have little influence over the things that happen to me."
    ]

    if request.method == 'POST':
        for i in range(1, 8):
            answer = request.form.get(f'locus_question_{i}')
            survey_response = SurveyResponse(
                user_id=user.id,
                scale='locus_of_control',
                task_number=i,
                question=questions[i-1],
                answer=answer
            )
            db.session.add(survey_response)
        db.session.commit()

        return redirect(url_for('demographic'))

    return render_template('locus.html', questions=questions)


"""
@app.route("/001/<int:question_n>", methods=['GET', 'POST'])
def trust(question_n):
    if not session.get('authenticated'):
        flash('You are not authenticated...', 'warning')
        return redirect(url_for('login'))

    user = Users.query.filter_by(id=session['access_code']).first()

    if user.treatment_gpt == 1:
        return redirect(url_for('loc', scale_number=1))

    questions = [
        "For routine transactions, I would rather interact with an artificially intelligent system than with a human.",
        "Artificial Intelligence can provide new economic opportunities for this country.",
        "Organisations use Artificial Intelligence unethically.",
        "Artificially intelligent systems can help people feel happier.",
        "I am impressed by what Artificial Intelligence can do.",
        "I think artificially intelligent systems make many errors.",
        "I am interested in using artificially intelligent systems in my daily life.",
        "I find Artificial Intelligence sinister.",
        "Artificial Intelligence might take control of people.",
        "I think Artificial Intelligence is dangerous.",
        "Artificial Intelligence can have positive impacts on people’s wellbeing.",
        "Artificial Intelligence is exciting.",
        "I would be grateful if you could select Strongly agree.",
        "An artificially intelligent agent would be better than an employee in many routine jobs.",
        "There are many beneficial applications of Artificial Intelligence.",
        "I shiver with discomfort when I think about future uses of Artificial Intelligence.",
        "Artificially intelligent systems can perform better than humans.",
        "Much of society will benefit from a future full of Artificial Intelligence.",
        "I would like to use Artificial Intelligence in my own job.",
        "People like me will suffer if Artificial Intelligence is used more and more.",
        "Artificial Intelligence is used to spy on people."
    ]

    if question_n > len(questions):
        return redirect(url_for('locus'))

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



@app.route("/loc/<int:scale_number>", methods=['GET', 'POST'])
def loc(scale_number):
    if not session.get('authenticated'):
        flash('You are not authenticated...', 'warning')
        return redirect(url_for('login'))

    user = Users.query.filter_by(id=session['access_code']).first()

    scales = [
        {
            'option_a': "Children get into trouble because their parents punish them too much.",
            'option_b': "The trouble with most children nowadays is that their parents are too easy with them.",
        },
        {
            'option_a': "Many of the unhappy things in people's lives are partly due to bad luck.",
            'option_b': "People's misfortunes result from the mistakes they make.",
        },
        {
            'option_a': "One of the major reasons why we have wars is because people don't take enough interest in politics.",
            'option_b': "There will always be wars, no matter how hard people try to prevent them.",
        },
        {
            'option_a': "In the long run people get the respect they deserve in this world.",
            'option_b': "Unfortunately, an individual's worth often passes unrecognized no matter how hard he tries.",
        },
        {
            'option_a': "The idea that teachers are unfair to students is nonsense.",
            'option_b': "Most students don't realize the extent to which their grades are influenced by accidental happenings.",
        },
        {
            'option_a': "Without the right breaks one cannot be an effective leader.",
            'option_b': "Capable people who fail to become leaders have not taken advantage of their opportunities.",
        },
        {
            'option_a': "No matter how hard you try some people just don't like you.",
            'option_b': "People who can't get others to like them don't understand how to get along with others.",
        },
        {
            'option_a': "Heredity plays the major role in determining one's personality.",
            'option_b': "It is one's experiences in life which determine what they're like.",
        },
        {
            'option_a': "I have often found that what is going to happen will happen.",
            'option_b': "Trusting to fate has never turned out as well for me as making a decision to take a definite course of action.",
        },
        {
            'option_a': "In the case of the well-prepared student there is rarely, if ever, such a thing as an unfair test.",
            'option_b': "Many times exam questions tend to be so unrelated to course work that studying is really useless.",
        },
        {
            'option_a': "Becoming a success is a matter of hard work, luck has little or nothing to do with it.",
            'option_b': "Getting a good job depends mainly on being in the right place at the right time.",
        },
        {
            'option_a': "The average citizen can have an influence in government decisions.",
            'option_b': "This world is run by the few people in power, and there is not much the little guy can do about it.",
        },
        {
            'option_a': "When I make plans, I am almost certain that I can make them work.",
            'option_b': "It is not always wise to plan too far ahead because many things turn out to be a matter of good or bad fortune anyhow.",
        },
        {
            'option_a': "There are certain people who are just no good.",
            'option_b': "There is some good in everybody.",
        },
        {
            'option_a': "In my case getting what I want has little or nothing to do with luck.",
            'option_b': "Many times we might just as well decide what to do by flipping a coin.",
        },
        {
            'option_a': "Who gets to be the boss often depends on who was lucky enough to be in the right place first.",
            'option_b': "Getting people to do the right thing depends upon ability. Luck has little or nothing to do with it.",
        },
        {
            'option_a': "As far as world affairs are concerned, most of us are the victims of forces we can neither understand nor control.",
            'option_b': "By taking an active part in political and social affairs, the people can control world events.",
        },
        {
            'option_a': "Most people don't realize the extent to which their lives are controlled by accidental happenings.",
            'option_b': "There really is no such thing as 'luck'.",
        },
        {
            'option_a': "One should always be willing to admit mistakes.",
            'option_b': "It is usually best to cover up one's mistakes.",
        },
        {
            'option_a': "It is hard to know whether or not a person really likes you.",
            'option_b': "How many friends you have depends upon how nice a person you are.",
        },
        {
            'option_a': "In the long run the bad things that happen to us are balanced by the good ones.",
            'option_b': "Most misfortunes are the result of lack of ability, ignorance, laziness, or all three.",
        },
        {
            'option_a': "With enough effort we can wipe out political corruption.",
            'option_b': "It is difficult for people to have much control over the things politicians do in office.",
        },
        {
            'option_a': "Sometimes I can't understand how teachers arrive at the grades they give.",
            'option_b': "There is a direct connection between how hard I study and the grades I get.",
        },
        {
            'option_a': "A good leader expects people to decide for themselves what they should do.",
            'option_b': "A good leader makes it clear to everybody what their jobs are.",
        },
        {
            'option_a': "Many times I feel that I have little influence over the things that happen to me.",
            'option_b': "It is impossible for me to believe that chance or luck plays an important role in my life.",
        },
        {
            'option_a': "People are lonely because they don't try to be friendly.",
            'option_b': "There's not much use in trying too hard to please people, if they like you, they like you.",
        },
        {
            'option_a': "There is too much emphasis on athletics in high school.",
            'option_b': "Team sports are an excellent way to build character.",
        },
        {
            'option_a': "What happens to me is my own doing.",
            'option_b': "Sometimes I feel that I don't have enough control over the direction my life is taking.",
        },
        {
            'option_a': "Most of the time I can't understand why politicians behave the way they do.",
            'option_b': "In the long run the people are responsible for bad government on a national as well as on a local level.",
        }
    ]

    # Redirect to the control page if all questions are completed
    if scale_number > len(scales):
        return redirect(url_for('demographic'))

    current_scale = scales[scale_number - 1]

    # Dynamically create the form with the current question's choices
    form = ChoiceForm()
    form.question.choices = [
        ('a', current_scale['option_a']),
        ('b', current_scale['option_b'])
    ]

    if request.method == 'POST' and form.validate():
        answer = form.question.data
        question_text = f"a. {current_scale['option_a']} / b. {current_scale['option_b']}"

        response = SurveyResponse(
            user_id=user.id,
            scale="rotters_loc",
            task_number=scale_number,
            question=question_text,
            answer=answer
        )
        db.session.add(response)
        db.session.commit()

        # Redirect to the next question
        return redirect(url_for('loc', scale_number=scale_number + 1))

    return render_template(
        'loc.html',
        form=form,
        scale_number=scale_number,
        total_questions=len(scales)
    )


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
"""


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
        return redirect(url_for('end'))

    return render_template("final.html", user=user, total_money=total_money)


@app.route("/end", methods=['GET', 'POST'])
def end():
    if not session.get('authenticated'):
        flash('You are not authenticated...', 'warning')
        return redirect(url_for('login'))

    return render_template("final1.html")


@app.route("/qualtrics", methods=["GET", "POST"])
def qualtrics():
    session['authenticated'] = False
    if 'access_code' in session:
        session.pop('access_code')
    if 'treatment_gpt' in session:
        session.pop('treatment_gpt')
    return redirect('https://ucplbusiness.co1.qualtrics.com/jfe/form/SV_54QO0eZywIczBbg')
