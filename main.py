import datetime
import os
import time

import requests
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, select, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase, Session

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

def main():
    url = 'https://are-we-there-yet.hackclub.com/'
    delay = 10

    while True:
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
                elapsed = 0.0
                if last and last.date:
                    elapsed = (now - last.date).total_seconds()
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
            print(f"Average pace: {pace:.4f}%/hour / {(pace / 60):.4f}%/minute")
            print(f"Last 10 minutes average pace: {pace:.4f}%/hour / {(pace / 60):.4f}%/minute")
            print(
                f"Migration completed in {f"{int((1 - progress_value) / pace)}"}h "
                f"{int((((1 - progress_value) / pace) - int((1 - progress_value) / pace)) * 60)} min "
                "at average pace"
                if pace > 0 else "N/A"
            )
            print(
                f"Migration completed in {f"{int((1 - progress_value) / pace_10min)}"}h "
                f"{int((((1 - progress_value) / pace_10min) - int((1 - progress_value) / pace_10min)) * 60)} min "
                "at last 10 minutes' average pace"
                if pace_10min > 0 else "N/A"
            )
            time.sleep(delay)
        except (ValueError, IndexError) as e:
            print(f"Error parsing progress: {e}")
        except KeyboardInterrupt:
            print("\nExiting...")
            break

if True:
    main()