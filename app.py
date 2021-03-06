# ----------------------------------------------------------------------------#
# Imports
# ----------------------------------------------------------------------------#

import json
import dateutil.parser
import babel
from flask import Flask, render_template, request, Response, flash, redirect, url_for
from flask_moment import Moment
from flask_sqlalchemy import SQLAlchemy
import logging
from logging import Formatter, FileHandler
from flask_wtf import Form
from forms import *
from flask_migrate import Migrate
from sqlalchemy import TypeDecorator
from sqlalchemy.dialects.postgresql import ARRAY, ENUM
from enum import Enum
import re

# ----------------------------------------------------------------------------#
# App Config.
# ----------------------------------------------------------------------------#

app = Flask(__name__)
moment = Moment(app)
app.config.from_object("config")
db = SQLAlchemy(app)

migrate = Migrate(app, db)

# ----------------------------------------------------------------------------#
# Models.
# ----------------------------------------------------------------------------#


class ArrayOfEnum(TypeDecorator):
    impl = ARRAY

    def bind_expression(self, bindvalue):
        return sa.cast(bindvalue, self)

    def result_processor(self, dialect, coltype):
        super_rp = super(ArrayOfEnum, self).result_processor(dialect, coltype)

        def handle_raw_string(value):
            inner = re.match(r"^{(.*)}$", value).group(1)
            return inner.split(",") if inner else []

        def process(value):
            if value is None:
                return None
            return super_rp(handle_raw_string(value))

        return process


class GenreType(Enum):
    jazz = "Jazz"
    classical = "Classical"
    reggae = "Reggae"
    swing = "Swing"
    folk = "Folk"
    r_b = "R&B"
    hip_hop = "Hip-Hop"
    rock_n_roll = "Rock n Roll"

    def __str__(self):
        return str(self.value)


class Venue(db.Model):
    __tablename__ = "Venue"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    genres = db.Column(ArrayOfEnum(ENUM(GenreType, name="genre_type")))
    city = db.Column(db.String(120))
    state = db.Column(db.String(120))
    address = db.Column(db.String(120))
    phone = db.Column(db.String(120))
    image_link = db.Column(db.String(500))
    website = db.Column(db.String(120))
    facebook_link = db.Column(db.String(120))
    seeking_talent = db.Column(db.Boolean)
    seeking_description = db.Column(db.Text)
    shows = db.relationship("Show", backref="venue", lazy=True)


class Artist(db.Model):
    __tablename__ = "Artist"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    city = db.Column(db.String(120))
    state = db.Column(db.String(120))
    phone = db.Column(db.String(120))
    genres = db.Column(ArrayOfEnum(ENUM(GenreType, name="genre_type")))
    image_link = db.Column(db.String(500))
    facebook_link = db.Column(db.String(120))
    website = db.Column(db.String(120))
    seeking_venue = db.Column(db.Boolean)
    seeking_description = db.Column(db.Text)
    shows = db.relationship("Show", backref="artist", lazy=True)


class Show(db.Model):
    __tablename__ = "Show"

    id = db.Column(db.Integer, primary_key=True)
    artist_id = db.Column(db.Integer, db.ForeignKey("Artist.id"), nullable=False)
    venue_id = db.Column(db.Integer, db.ForeignKey("Venue.id"), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)


# ----------------------------------------------------------------------------#
# Filters.
# ----------------------------------------------------------------------------#


def format_datetime(value, format="medium"):
    date = dateutil.parser.parse(value)
    if format == "full":
        format = "EEEE MMMM, d, y 'at' h:mma"
    elif format == "medium":
        format = "EE MM, dd, y h:mma"
    return babel.dates.format_datetime(date, format)


app.jinja_env.filters["datetime"] = format_datetime

# ----------------------------------------------------------------------------#
# Helper Functions
# ----------------------------------------------------------------------------#


def sortUpcomingShows(shows, now, isArtist=False):
    sortedShows = {"past": [], "upcoming": []}
    for show in shows:
        # Check if sorting for artist or venue route
        if isArtist:
            showDict = {
                "venue_id": show.venue.id,
                "venue_name": show.venue.name,
                "venue_image_link": show.venue.image_link,
                "start_time": show.start_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            }
        else:
            showDict = {
                "artist_id": show.artist.id,
                "artist_name": show.artist.name,
                "artist_image_link": show.artist.image_link,
                "start_time": show.start_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            }
        if show.start_time > now:
            sortedShows["upcoming"].append(showDict)
        else:
            sortedShows["past"].append(showDict)
    return sortedShows


def countIsUpcoming(shows, now):
    result = 0
    for show in shows:
        if show.start_time > now:
            result += 1
    return result


# ----------------------------------------------------------------------------#
# Controllers.
# ----------------------------------------------------------------------------#


@app.route("/")
def index():
    return render_template("pages/home.html")


#  Venues
#  ----------------------------------------------------------------


@app.route("/venues")
def venues():
    # Query data from Venue table in db
    dbData = Venue.query.all()
    now = datetime.now()

    # Transform data into dictionary
    venuesDict = {}
    for venue in dbData:
        if (venue.city, venue.state) not in venuesDict:
            venuesDict[venue.city, venue.state] = [
                {
                    "id": venue.id,
                    "name": venue.name,
                    "num_upcoming_shows": countIsUpcoming(venue.shows, now),
                }
            ]
        else:
            venuesDict[venue.city, venue.state].append(
                {
                    "id": venue.id,
                    "name": venue.name,
                    "num_upcoming_shows": countIsUpcoming(venue.shows, now),
                }
            )

    data = [
        {"city": city, "state": state, "venues": venuesDict[city, state],}
        for city, state in venuesDict
    ]
    return render_template("pages/venues.html", areas=data)


@app.route("/venues/search", methods=["POST"])
def search_venues():
    searchTerm = request.form.get("search_term", "")
    dbData = Venue.query.filter(Venue.name.ilike(f"%{searchTerm}%")).all()
    now = datetime.now()
    response = {
        "count": len(dbData),
        "data": [
            {
                "id": result.id,
                "name": result.name,
                "num_upcoming_shows": countIsUpcoming(result.shows, now),
            }
            for result in dbData
        ],
    }
    return render_template(
        "pages/search_venues.html", results=response, search_term=searchTerm,
    )


@app.route("/venues/<int:venue_id>")
def show_venue(venue_id):
    # shows the venue page with the given venue_id
    dbData = (
        Venue.query.join(Show, isouter=True)
        .join(Artist, isouter=True)
        .filter(Venue.id == venue_id)
        .first()
    )
    now = datetime.now()
    # Sort shows based on start_time into whether upcoming or past
    sortedShows = sortUpcomingShows(dbData.shows, now)

    # Transform data into format for view to render
    parsedData = {
        "id": dbData.id,
        "name": dbData.name,
        "genres": dbData.genres,
        "address": dbData.address,
        "city": dbData.city,
        "state": dbData.state,
        "phone": dbData.phone,
        "website": dbData.website,
        "facebook_link": dbData.facebook_link,
        "seeking_talent": dbData.seeking_talent,
        "seeking_description": dbData.seeking_description,
        "image_link": dbData.image_link,
        "past_shows": sortedShows["past"],
        "upcoming_shows": sortedShows["upcoming"],
        "past_shows_count": len(sortedShows["past"]),
        "upcoming_shows_count": len(sortedShows["upcoming"]),
    }

    return render_template("pages/show_venue.html", venue=parsedData)


#  Create Venue
#  ----------------------------------------------------------------


@app.route("/venues/create", methods=["GET"])
def create_venue_form():
    form = VenueForm()
    return render_template("forms/new_venue.html", form=form)


@app.route("/venues/create", methods=["POST"])
def create_venue_submission():
    # TODO: insert form data as a new Venue record in the db, instead
    # TODO: modify data to be the data object returned from db insertion

    # on successful db insert, flash success
    flash("Venue " + request.form["name"] + " was successfully listed!")
    # TODO: on unsuccessful db insert, flash an error instead.
    # e.g., flash('An error occurred. Venue ' + data.name + ' could not be listed.')
    # see: http://flask.pocoo.org/docs/1.0/patterns/flashing/
    return render_template("pages/home.html")


@app.route("/venues/<venue_id>", methods=["DELETE"])
def delete_venue(venue_id):
    # TODO: Complete this endpoint for taking a venue_id, and using
    # SQLAlchemy ORM to delete a record. Handle cases where the session commit could fail.

    # BONUS CHALLENGE: Implement a button to delete a Venue on a Venue Page, have it so that
    # clicking that button delete it from the db then redirect the user to the homepage
    return None


#  Artists
#  ----------------------------------------------------------------
@app.route("/artists")
def artists():
    dbData = Artist.query.all()
    return render_template("pages/artists.html", artists=dbData)


@app.route("/artists/search", methods=["POST"])
def search_artists():
    # seach for "A" should return "Guns N Petals", "Matt Quevado", and "The Wild Sax Band".
    # search for "band" should return "The Wild Sax Band".
    searchTerm = request.form.get("search_term", "")
    dbData = Artist.query.filter(Artist.name.ilike(f"%{searchTerm}%")).all()
    now = datetime.now()
    response = {
        "count": len(dbData),
        "data": [
            {
                "id": result.id,
                "name": result.name,
                "num_upcoming_shows": countIsUpcoming(result.shows, now),
            }
            for result in dbData
        ],
    }
    return render_template(
        "pages/search_artists.html", results=response, search_term=searchTerm,
    )


@app.route("/artists/<int:artist_id>")
def show_artist(artist_id):
    # shows the artist page with the given artist_id
    dbData = (
        Artist.query.join(Show, isouter=True)
        .join(Venue, isouter=True)
        .filter(Artist.id == artist_id)
        .first()
    )
    now = datetime.now()
    # Sort shows based on start_time into whether upcoming or past
    sortedShows = sortUpcomingShows(dbData.shows, now, True)
    parsedData = {
        "id": dbData.id,
        "name": dbData.name,
        "genres": dbData.genres,
        "city": dbData.city,
        "state": dbData.state,
        "phone": dbData.phone,
        "website": dbData.website,
        "facebook_link": dbData.facebook_link,
        "seeking_venue": dbData.seeking_venue,
        "seeking_description": dbData.seeking_description,
        "image_link": dbData.image_link,
        "past_shows": sortedShows["past"],
        "upcoming_shows": sortedShows["upcoming"],
        "past_shows_count": len(sortedShows["past"]),
        "upcoming_shows_count": len(sortedShows["upcoming"]),
    }

    return render_template("pages/show_artist.html", artist=parsedData)


#  Update
#  ----------------------------------------------------------------
@app.route("/artists/<int:artist_id>/edit", methods=["GET"])
def edit_artist(artist_id):
    form = ArtistForm()
    artist = {
        "id": 4,
        "name": "Guns N Petals",
        "genres": ["Rock n Roll"],
        "city": "San Francisco",
        "state": "CA",
        "phone": "326-123-5000",
        "website": "https://www.gunsnpetalsband.com",
        "facebook_link": "https://www.facebook.com/GunsNPetals",
        "seeking_venue": True,
        "seeking_description": "Looking for shows to perform at in the San Francisco Bay Area!",
        "image_link": "https://images.unsplash.com/photo-1549213783-8284d0336c4f?ixlib=rb-1.2.1&ixid=eyJhcHBfaWQiOjEyMDd9&auto=format&fit=crop&w=300&q=80",
    }
    # TODO: populate form with fields from artist with ID <artist_id>
    return render_template("forms/edit_artist.html", form=form, artist=artist)


@app.route("/artists/<int:artist_id>/edit", methods=["POST"])
def edit_artist_submission(artist_id):
    # TODO: take values from the form submitted, and update existing
    # artist record with ID <artist_id> using the new attributes

    return redirect(url_for("show_artist", artist_id=artist_id))


@app.route("/venues/<int:venue_id>/edit", methods=["GET"])
def edit_venue(venue_id):
    form = VenueForm()
    venue = {
        "id": 1,
        "name": "The Musical Hop",
        "genres": ["Jazz", "Reggae", "Swing", "Classical", "Folk"],
        "address": "1015 Folsom Street",
        "city": "San Francisco",
        "state": "CA",
        "phone": "123-123-1234",
        "website": "https://www.themusicalhop.com",
        "facebook_link": "https://www.facebook.com/TheMusicalHop",
        "seeking_talent": True,
        "seeking_description": "We are on the lookout for a local artist to play every two weeks. Please call us.",
        "image_link": "https://images.unsplash.com/photo-1543900694-133f37abaaa5?ixlib=rb-1.2.1&ixid=eyJhcHBfaWQiOjEyMDd9&auto=format&fit=crop&w=400&q=60",
    }
    # TODO: populate form with values from venue with ID <venue_id>
    return render_template("forms/edit_venue.html", form=form, venue=venue)


@app.route("/venues/<int:venue_id>/edit", methods=["POST"])
def edit_venue_submission(venue_id):
    # TODO: take values from the form submitted, and update existing
    # venue record with ID <venue_id> using the new attributes
    return redirect(url_for("show_venue", venue_id=venue_id))


#  Create Artist
#  ----------------------------------------------------------------


@app.route("/artists/create", methods=["GET"])
def create_artist_form():
    form = ArtistForm()
    return render_template("forms/new_artist.html", form=form)


@app.route("/artists/create", methods=["POST"])
def create_artist_submission():
    # called upon submitting the new artist listing form
    # TODO: insert form data as a new Venue record in the db, instead
    # TODO: modify data to be the data object returned from db insertion

    # on successful db insert, flash success
    flash("Artist " + request.form["name"] + " was successfully listed!")
    # TODO: on unsuccessful db insert, flash an error instead.
    # e.g., flash('An error occurred. Artist ' + data.name + ' could not be listed.')
    return render_template("pages/home.html")


#  Shows
#  ----------------------------------------------------------------


@app.route("/shows")
def shows():
    # displays list of shows at /shows
    dbData = Show.query.join("artist").join("venue").all()
    data = [
        {
            "venue_id": show.venue.id,
            "venue_name": show.venue.name,
            "artist_id": show.artist.id,
            "artist_name": show.artist.name,
            "artist_image_link": show.artist.image_link,
            "start_time": show.start_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        }
        for show in dbData
    ]
    return render_template("pages/shows.html", shows=data)


@app.route("/shows/create")
def create_shows():
    # renders form. do not touch.
    form = ShowForm()
    return render_template("forms/new_show.html", form=form)


@app.route("/shows/create", methods=["POST"])
def create_show_submission():
    # called to create new shows in the db, upon submitting new show listing form
    # TODO: insert form data as a new Show record in the db, instead

    # on successful db insert, flash success
    flash("Show was successfully listed!")
    # TODO: on unsuccessful db insert, flash an error instead.
    # e.g., flash('An error occurred. Show could not be listed.')
    # see: http://flask.pocoo.org/docs/1.0/patterns/flashing/
    return render_template("pages/home.html")


@app.errorhandler(404)
def not_found_error(error):
    return render_template("errors/404.html"), 404


@app.errorhandler(500)
def server_error(error):
    return render_template("errors/500.html"), 500


if not app.debug:
    file_handler = FileHandler("error.log")
    file_handler.setFormatter(
        Formatter("%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]")
    )
    app.logger.setLevel(logging.INFO)
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.info("errors")

# ----------------------------------------------------------------------------#
# Launch.
# ----------------------------------------------------------------------------#

# Default port:
if __name__ == "__main__":
    app.run()

# Or specify port manually:
"""
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
"""
