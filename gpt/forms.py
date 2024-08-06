from flask_wtf import FlaskForm
from wtforms import RadioField, validators, FloatField, SubmitField, IntegerField, FieldList, SelectField
from wtforms.validators import DataRequired, NumberRange
from datetime import datetime


def read_countries_from_file(file_path):
    with open(file_path, 'r') as file:
        return [line.strip() for line in file if line.strip()]


class MultipleChoiceForm(FlaskForm):
    question = RadioField('Question', validators=[validators.DataRequired()])
    submit = SubmitField('Submit')

    def __init__(self, *args, **kwargs):
        super(MultipleChoiceForm, self).__init__(*args, **kwargs)
        choices = kwargs.get('choices')
        if choices:
            self.question.choices = choices


class NumericalAnswerForm(FlaskForm):
    answer = FloatField('Answer', validators=[validators.input_required()])
    submit = SubmitField('Submit')


class ScaleForm(FlaskForm):
    question = RadioField('Question', validators=[validators.DataRequired()])
    submit = SubmitField('Submit')

    def __init__(self, *args, **kwargs):
        super(ScaleForm, self).__init__(*args, **kwargs)
        choices = kwargs.get('choices')
        if choices:
            self.question.choices = choices


class AttitudeForm(FlaskForm):
    slider = IntegerField('Slider', validators=[validators.NumberRange(min=1, max=7)])
    submit = SubmitField('Submit', render_kw={"class": "btn btn-primary mt-3"})


class ControlForm(FlaskForm):
    answers = FieldList(IntegerField('Answer', validators=[validators.NumberRange(min=1, max=7)]), min_entries=6)
    submit = SubmitField('Submit', render_kw={"class": "btn btn-primary mt-3"})


class LikertScaleForm(FlaskForm):
    question = RadioField('Question', choices=[
        ('1', '1. Strongly disagree'),
        ('2', '2. Somewhat disagree'),
        ('3', '3. Neutral'),
        ('4', '4. Somewhat agree'),
        ('5', '5. Strongly agree')
    ], validators=[validators.DataRequired()])
    submit = SubmitField('Submit', render_kw={"class": "btn btn-primary mt-3"})


class DemographicsForm(FlaskForm):
    current_year = datetime.now().year
    age = IntegerField('Age', validators=[
        DataRequired(),
        NumberRange(min=18, max=100, message="Please enter a valid age")
    ])
    gender = SelectField('Gender', choices=[
        ('', 'Select gender'),
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer_not_to_say', 'Prefer not to say')
    ], validators=[DataRequired()])
    education = SelectField('Highest Level of Education', choices=[
        ('', 'Select level of education'),
        ('high_school', 'High School'),
        ('bachelors', 'Bachelor\'s Degree'),
        ('masters', 'Master\'s Degree'),
        ('doctorate', 'Doctorate'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    country = SelectField('Country of Residence', choices=[], validators=[DataRequired()])
    submit = SubmitField('Submit')

    def __init__(self, *args, **kwargs):
        super(DemographicsForm, self).__init__(*args, **kwargs)
        countries = read_countries_from_file('gpt/static/countries.txt')
        self.country.choices = [('', 'Select a country')] + [(country, country) for country in countries]
