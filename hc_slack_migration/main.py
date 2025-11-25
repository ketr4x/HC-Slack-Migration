import datetime
import os
import time
import requests
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, select, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase, Session
import argparse

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

engine = create_engine("sqlite:///progress.db")

class Base(DeclarativeBase):
    pass

class Progress(Base):
    __tablename__ = 'progress'
    date: Mapped[datetime.datetime] = mapped_column(DateTime, primary_key=True)
    progress: Mapped[float] = mapped_column(Float)

Base.metadata.create_all(engine)

def parse_args():
    parser = argparse.ArgumentParser(description='Monitor Hack Club Slack migration progress')
    parser.add_argument('--url', type=str, default='https://are-we-there-yet.hackclub.com/',
                        help='URL to monitor (default: https://are-we-there-yet.hackclub.com/)')
    parser.add_argument('--delay', type=int, default=10, help='Delay between checks in seconds (default:10)')
    return parser.parse_args()

def main():
    args = parse_args()
    url = args.url
    delay = args.delay
    with Session(engine) as session:
        last = session.execute(select(Progress).order_by(Progress.date.desc())).scalars().first()
        completed = int(last.progress) == 1
        session.commit()

    while not completed:
        try:
            response = requests.get(url)
            if response.status_code != 200:
                print(f'Error with getting a response: {response}')
                time.sleep(delay)
                continue

            soup = BeautifulSoup(response.text, 'html.parser')
            current_progress = soup.find_all('div', class_='progress-text')
            if not current_progress:
                print(f'Error with parsing a value: {response}')
                time.sleep(delay)
                continue

            progress_value = float(current_progress[0].text.strip().rstrip("%").strip()) / 100

            with Session(engine) as session:
                first = session.execute(select(Progress).order_by(Progress.date.asc())).scalars().first()
                last = session.execute(select(Progress).order_by(Progress.date.desc())).scalars().first()
                now = datetime.datetime.now()
                new_progress = Progress(
                    date=now,
                    progress=progress_value
                )

                pace = 0.0
                if first and last and first.date != last.date:
                    total_elapsed = (last.date - first.date).total_seconds()
                    progress_change = last.progress - first.progress
                    pace = (progress_change / total_elapsed * 3600) if total_elapsed > 0 else 0.0

                ten_minutes_ago = now - datetime.timedelta(minutes=10)
                recent_records = session.execute(
                    select(Progress)
                    .where(Progress.date >= ten_minutes_ago)
                    .order_by(Progress.date.asc())
                ).scalars().all()

                pace_10min = 0.0
                if len(recent_records) >= 2:
                    first_recent = recent_records[0]
                    last_recent = recent_records[-1]
                    time_diff = (last_recent.date - first_recent.date).total_seconds()
                    progress_diff = last_recent.progress - first_recent.progress
                    pace_10min = (progress_diff / time_diff * 3600) if time_diff > 0 else 0.0

                session.add(new_progress)
                session.commit()

            clear_screen()
            print(f"Total progress: {progress_value * 100:.2f}%")
            print(f"Average pace: {pace*24:.4f}%/day / {pace:.4f}%/hour / {(pace / 60):.4f}%/minute / {(pace / 60 / 60):.8f}%/second")
            print(f"Last 10 minutes average pace: {pace_10min*24:.4f}%/day / {pace_10min:.4f}%/hour / {(pace_10min / 60):.4f}%/minute / {(pace_10min / 60 / 60):.8f}%/second")
            if pace > 0:
                remaining_hours = (1 - progress_value) / pace
                days = int(remaining_hours // 24)
                hours = int(remaining_hours % 24)
                remaining_minutes = (remaining_hours - int(remaining_hours)) * 60
                minutes = int(remaining_minutes)
                seconds = int((remaining_minutes - minutes) *60)
                print(f"Migration will be completed in {f"{days}d " if days else ''}{f"{hours}h " if hours else ''}{f"{minutes}m " if minutes else ''}{f"{seconds}s" if seconds else ''} at average pace")
            else:
                print('N/A')
            if pace_10min > 0:
                remaining_hours_10 = (1 - progress_value) / pace_10min
                days_10 = int(remaining_hours_10 // 24)
                hours_10 = int(remaining_hours_10 % 24)
                remaining_minutes_10 = (remaining_hours_10 - int(remaining_hours_10)) * 60
                minutes_10 = int(remaining_minutes_10)
                seconds_10 = int((remaining_minutes_10 - minutes_10) * 60)
                print(f"Migration will be completed in {f"{days_10}d " if days_10 else ''}{f"{hours_10}h " if hours_10 else ''}{f"{minutes_10}m " if minutes_10 else ''}{f"{seconds_10}s" if seconds_10 else ''} at last 10 minutes' pace")
            else:
                print('N/A')
            time.sleep(delay)

        except (ValueError, IndexError) as e:
            print(f"Error parsing progress: {e}")
        except KeyboardInterrupt:
            print("\nExiting...")
            break

    if completed:
        with Session(engine) as session:
            first = session.execute(select(Progress).order_by(Progress.date.asc())).scalars().first()
            last = session.execute(select(Progress).order_by(Progress.date.desc())).scalars().first()
            total_elapsed = (last.date - first.date).total_seconds()
            progress_change = last.progress - first.progress
            pace = (progress_change / total_elapsed * 3600) if total_elapsed > 0 else 0.0
            session.commit()
        remaining_hours = 1 / pace
        days = int(remaining_hours // 24)
        hours = int(remaining_hours % 24)
        remaining_minutes = (remaining_hours - int(remaining_hours)) * 60
        minutes = int(remaining_minutes)
        seconds = int((remaining_minutes - minutes) *60)
        clear_screen()
        print("Migration completed")
        print(f"Average pace: {pace*24:.4f}%/day / {pace:.4f}%/hour / {(pace / 60):.4f}%/minute / {(pace / 60 / 60):.8f}%/second")
        print(f"Estimated migration time: {f"{days}d " if days else ''}{f"{hours}h " if hours else ''}{f"{minutes}m " if minutes else ''}{f"{seconds}s" if seconds else ''}")

if __name__ == "__main__":
    main()