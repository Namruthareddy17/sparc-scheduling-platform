from flask import Flask, render_template, redirect, url_for, request, flash, session , jsonify
from flask_sqlalchemy import SQLAlchemy
import random
import os
from werkzeug.utils import secure_filename


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
db = SQLAlchemy(app)

# Define models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    bookings = db.relationship('Booking', backref='user', lazy=True)

class Provider(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    service = db.Column(db.String(120), nullable=False)
    rating = db.Column(db.Float, nullable=False)
    image = db.Column(db.String(120), nullable=True)  # Field to store image file name
    bookings = db.relationship('Booking', backref='provider', lazy=True)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    provider_id = db.Column(db.Integer, db.ForeignKey('provider.id'))
    date = db.Column(db.String(10))  # Store the date
    time_slot = db.Column(db.String(10))  # Store the time slot

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def get_chatbot_response(user_input):
    # Convert the user input to lowercase to make the matching case-insensitive
    user_input = user_input.lower()

    # If the user says "hi", respond with "How can I help you?"
    if 'hi' in user_input or 'hello' in user_input:
        return "How can I help you?"

    # If the user asks for "best" or "most rated", provide the top provider based on ratings
    if 'best' in user_input or 'most rated' in user_input:
        # Assuming the user is looking for the top-rated provider
        providers = Provider.query.all()

        if providers:
            # Sort providers by rating in descending order
            providers.sort(key=lambda x: x.rating, reverse=True)

            # Limit to the top 1 provider
            top_provider = providers[0]
            
            # Create a clickable link for provider details
            response = f"""
            <b>Provider:</b> {top_provider.name}<br>
            <b>Service:</b> {top_provider.service}<br>
            <b>Rating:</b> {top_provider.rating}<br>
            <b>Details:</b> <a href="{url_for('provider_details', provider_id=top_provider.id)}">Click here</a>
            """
            return response

        else:
            return "Sorry, no providers found."

    # For any other input, return a default "sorry" message
    return "Sorry, I didn't understand that."

# Home page route
@app.route('/')
def home():
    providers = Provider.query.all()
    return render_template('home.html', providers=providers)

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.json.get('message')
    if user_input:
        response = get_chatbot_response(user_input)
        return jsonify({'response': response})
    return jsonify({'response': 'Sorry, I didn\'t understand that.'})

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query')  # Get the search query from the URL

    if query:
        # Search by provider name or service
        providers = Provider.query.filter(
            (Provider.name.ilike(f'%{query}%')) | 
            (Provider.service.ilike(f'%{query}%'))
        ).all()
    else:
        # If no search query, return all providers
        providers = Provider.query.all()

    return render_template('home.html', providers=providers)

# My Bookings page route
@app.route('/my_bookings')
def my_bookings():
    if 'user_id' not in session:
        flash('Please log in to view your bookings.', 'danger')
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])

    if not user:
        flash('User not found. Please log in again.', 'danger')
        session.pop('user_id', None)  # clear any stale session
        return redirect(url_for('login'))

    bookings = Booking.query.filter_by(user_id=user.id).all()
    return render_template('my_bookings.html', bookings=bookings)


# Login page route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:
            session['user_id'] = user.id
            return redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check username and password.', 'danger')
    return render_template('login.html')

# Signup page route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists. Please choose another one.', 'danger')
            return redirect(url_for('signup'))
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        flash('Account created successfully!', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')

# Provider registration route
@app.route('/provider_register', methods=['GET', 'POST'])
def provider_register():
    if request.method == 'POST':
        try:
            name = request.form['name']
            service = request.form['service']
            rating = request.form['rating']
            image = request.files['image']  # Get the image from the form
            
            if image and allowed_file(image.filename):
                filename = secure_filename(image.filename)
                image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_url = f'uploads/{filename}'  # Store relative URL for the image
            else:
                image_url = None  # No image provided or invalid extension
            
            # Add the provider to the database
            new_provider = Provider(name=name, service=service, rating=float(rating), image=image_url)
            db.session.add(new_provider)
            db.session.commit()
            flash('Provider registered successfully!', 'success')
            return redirect(url_for('home'))
        except KeyError as e:
            flash(f"Missing form field: {str(e)}", 'danger')
            return render_template('provider_register.html')

    return render_template('provider_register.html')

# Booking route
@app.route('/book/<int:provider_id>/<date>/<time_slot>', methods=['POST'])
def book(provider_id, date, time_slot):
    if 'user_id' not in session:
        flash('Please log in to book a service!', 'danger')
        return redirect(url_for('login'))

    user = User.query.get(session.get('user_id'))
    provider = Provider.query.get(provider_id)

    if not user or not provider:
        flash('Booking failed. Please try again.', 'danger')
        return redirect(url_for('home'))

    # Save the booking with date and time slot
    booking = Booking(user_id=user.id, provider_id=provider.id, date=date, time_slot=time_slot)
    db.session.add(booking)
    db.session.commit()

    flash('Booking successful!', 'success')
    return redirect(url_for('my_bookings'))


# Provider details route
@app.route('/provider/<int:provider_id>')
def provider_details(provider_id):
    provider = Provider.query.get_or_404(provider_id)
    return render_template('provider_details.html', provider=provider)

# Logout route
@app.route('/logout')
def logout():
    # Clear the session to log out the user
    session.pop('user_id', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('home'))

@app.route('/payment/<int:provider_id>/<date>/<time_slot>', methods=['GET', 'POST'])
def payment(provider_id, date, time_slot):
    if 'user_id' not in session:
        flash('Please log in to continue.', 'danger')
        return redirect(url_for('login'))

    provider = Provider.query.get_or_404(provider_id)

    if request.method == 'POST':
        # Payment is "successful", now create booking
        booking = Booking(
            user_id=session['user_id'],
            provider_id=provider.id,
            date=date,
            time_slot=time_slot
        )
        db.session.add(booking)
        db.session.commit()
        flash('Payment successful! Booking confirmed.', 'success')
        return redirect(url_for('my_bookings'))

    return render_template('payment.html', provider=provider, date=date, time_slot=time_slot)

# Ensure this is inside the application context
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
