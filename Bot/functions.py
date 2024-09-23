# discord imports
import discord
from discord.ext import commands 

# python imports
from dotenv import load_dotenv
import os
import re

# 3rd party imports
import mysql.connector
from mysql.connector import Error
from mysql.connector.abstracts import MySQLConnectionAbstract
from mysql.connector.pooling import PooledMySQLConnection
import yt_dlp


load_dotenv()
DATABASE_ENDPOINT = os.getenv("DATABASE_ENDPOINT")
DATABASE_USER = os.getenv("DATABASE_USERNAME")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD")
DATABASE_PORT = os.getenv("DATABASE_PORT")


def load_ids() -> dict[int, dict[str, int]]:
    # load the ids from the database
    connection = create_connection("Servers")
    query = "SELECT * FROM guilds"
    result = select_query(connection, query, [])
    if result:
        ids = {}
        for guild in result:
            server_id = guild["server_id"]
            ids[server_id] = {
                "owner_id": guild["owner_id"],
                "sancturary_keeper_role_id": guild["sancturary_keeper_role_id"],
                "sky_guardians_role_id": guild["sky_guardians_role_id"],
                "tech_oracle_role_id": guild["tech_oracle_role_id"],
                "event_luminary_role_id": guild["event_luminary_role_id"],
                "assistaint_role_id": guild["assistaint_role_id"],
                "support_category_id": guild["support_category_id"],
                "general_category_id": guild["general_category_id"],
                "music_voice_id": guild["music_voice_id"],
                "bot_channel_id": guild["bot_channel_id"],
                "music_channel_id": guild["music_channel_id"],
                "ticket_channel_id": guild["ticket_channel_id"],
                "ticket_log_channel_id": guild["ticket_log_channel_id"]
            }
        close_connection(connection)
        return ids
    print("[error][functions] No IDs found in the database.")
    raise Exception("No IDs found in the database.")

# Function to send the response
async def send_message_to_user(client: commands.Bot, user_id: int, message: str) -> None:
    if not message:
        print("User message is empty.")
        return

    try:
        # Assuming get_response is defined in responses.py and returns a string
        user = client.get_user(user_id)
        await user.send(str(message))
    
    except Exception as e:
        print(f"\n[error][functions] An error occurred while trying to send an message: {e}\n")


# Function to save the transcript of a ticket
async def save_transcript(channel: discord.TextChannel, ticket_logs: str) -> None:
    dir = os.path.dirname(__file__)
    path = f"{dir}/tickets/ticket-{channel.name}.txt"
    os.makedirs(os.path.dirname(path), exist_ok=True)

    try:
        # Open the file with UTF-8 encoding and handle any encoding errors gracefully
        with open(path, "w", encoding="utf-8", errors="replace") as f:
            print(f"[tickets] Writing transcript for ticket {channel.name}")
            async for message in channel.history(limit=None):
                # Append the message with the author's name to the logs
                ticket_logs = f"{message.author.name}: {message.content}\n" + ticket_logs
            ticket_logs = f"Transcript for {channel.name}:\n" + "```\n" + ticket_logs + "```"
            f.write(ticket_logs)
        return path
    except Exception as e:
        print(f"Error saving transcript for {channel.name}: {e}")


# Function to create MySQL database connection
def create_connection(database_name: str) -> mysql.connector.connection.MySQLConnection:
    connection = None
    try:
        connection: PooledMySQLConnection | MySQLConnectionAbstract = mysql.connector.connect(
            host=DATABASE_ENDPOINT,
            user=DATABASE_USER,
            password=DATABASE_PASSWORD,
            database=database_name,
            port=DATABASE_PORT
        )
        if connection.is_connected():
            print(f"Connection to MySQL {database_name} DB successful")
    except Error as e:
        print(f"The error '{e}' occurred")
    return connection


# Insert query function
def insert_query(connection: PooledMySQLConnection | MySQLConnectionAbstract, query, values):
    cursor = connection.cursor()
    try:
        cursor.execute(query, values)
        connection.commit()
        print("Query executed successfully")
    except Error as e:
        print(f"The error '{e}' occurred")


# Select query function
def select_query(connection: PooledMySQLConnection | MySQLConnectionAbstract, query, values=None):
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(query, values)
        result = cursor.fetchall()
        return result
    except Error as e:
        print(f"The error '{e}' occurred")


# Update query function
def update_query(connection: PooledMySQLConnection | MySQLConnectionAbstract, query, values):
    cursor = connection.cursor()
    try:
        cursor.execute(query, values)
        connection.commit()
        print("Query executed successfully")
    except Error as e:
        print(f"The error '{e}' occurred")


# Delete query function
def delete_query(connection: PooledMySQLConnection | MySQLConnectionAbstract, query, values):
    cursor = connection.cursor()
    try:
        cursor.execute(query, values)
        connection.commit()
        print("Query executed successfully")
    except Error as e:
        print(f"The error '{e}' occurred")


# Close MySQL connection
def close_connection(connection: PooledMySQLConnection | MySQLConnectionAbstract):
    if connection.is_connected():
        connection.close()
        print("The connection is closed")


def save_ticket_to_db(connection: PooledMySQLConnection | MySQLConnectionAbstract, user_id: int, channel_id: int):
    query = "INSERT INTO open_tickets (user_id, channel_id) VALUES (%s, %s)"
    values = (user_id, channel_id)
    insert_query(connection, query, values)


def load_ticket_from_db(connection: PooledMySQLConnection | MySQLConnectionAbstract, channel_id: int):
    query = "SELECT user_id FROM open_tickets WHERE channel_id = %s"
    result = select_query(connection, query, (channel_id,))
    if result:
        return result[0]  # Return the first matching ticket record
    return None


def delete_ticket_from_db(connection: PooledMySQLConnection | MySQLConnectionAbstract, channel_id: int):
    query = "DELETE FROM open_tickets WHERE channel_id = %s"
    delete_query(connection, query, (channel_id,))


# Function to get the video URLs from a playlist
def get_video_urls_from_playlist(playlist_url):
    ydl_opts: dict[str, bool] = {
        'extract_flat': True,  # Only extract the URL, no downloads
        'quiet': True  # Suppress output
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info_dict = ydl.extract_info(playlist_url, download=False)
            video_urls = [entry['url'] for entry in info_dict['entries']]
            playlist_title = info_dict['title']
            return video_urls, playlist_title
        except Exception as e:
            print(f"Error: {e}")
            return []


# Main function
def get_video_urls(url: str) -> list:
    playlist_pattern = r'(?:https?://)?(?:www\.)?youtube\.com/playlist\?list=[\w-]+'
    radio_pattern = r"^https?:\/\/(www\.)?youtube\.com\/.*[?&]list=(RD|RDEM)[^&]+.*"
    video_pattern = r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[\w-]+'

    if re.match(playlist_pattern, url):
        video_urls, playlist_title = get_video_urls_from_playlist(url)
        if not video_urls:
            print("[error] No videos found or failed to fetch URLs.")
            return []
        return video_urls

    elif re.match(radio_pattern, url):
        print("[warning] The provided URL is a radio URL and cannot be processed.")
        return "radio"

    elif re.match(video_pattern, url):
        return [url]

    else:
        print("[warning] The provided URL is not a valid YouTube playlist or video URL.")
        return []