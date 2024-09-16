import traceback
import chime
import streamlit as st
from typing import List
import time as python_time
import argparse

from ktrains.korail.korail import AdultPassenger, Korail
from ktrains.korail.korail import ReserveOption as ReserveOptionKorail
from ktrains.srt.seat_type import SeatType as ReserveOptionSRT
from ktrains.srt.srt import SRT
from ktrains.utils import save_to_log
from ktrains.manage import (
    manage_available,
    manage_unavailable,
    manage_reservation,
    manage_error,
    manage_start,
)


def get_trains(
    id: str,
    pw: str,
    email_receivers: List[str],
    dep: str,
    arr: str,
    date: str,
    time: str,
    train_nos: List[str],
    mode: str = "korail",
    notify: bool = True,
    reserve: bool = True,
    number_of_tickets: int = 1,
    number_of_tries: int = 10,
    timeout: int = 5,
    email_sender: str = None,
    email_password: str = None,
    seat_type: str = "B",
):
    """
    Main function to run the script. This function will run forever until the number of tickets is reserved or the number of tries is reached.

    Args:
        id (str): Korail or SRT ID
        pw (str): Korail or SRT password
        email_receivers (str): comma separated list of email receivers
        dep (str): departure station
        arr (str): arrival station
        date (str): date of travel in YYYYMMDD format
        time (str): time of travel in HHMM format
        train_nos (str): comma separated list of train numbers
        mode (str, optional): korail or srt. Defaults to "korail".
        notify (bool, optional): whether to send email notifications. Defaults to True.
        reserve (bool, optional): whether to reserve tickets. Defaults to False.
        number_of_tickets (int, optional): number of tickets to reserve. Defaults to 1.
        number_of_tries (int, optional): number of tries to search for trains. Defaults to 10.
        timeout (int, optional): timeout between each search. Defaults to 5.
        email_sender (str, optional): email sender. Defaults to None.
        email_password (str, optional): email password. Defaults to None.
    """
    try:
        print("Running main script!")

        if isinstance(notify, str):
            notify = notify.lower() == "true"
        if isinstance(reserve, str):
            reserve = reserve.lower() == "true"

        if email_sender is None:
            email_sender = st.secrets.get("email_sender")
        if email_password is None:
            email_password = st.secrets.get("email_password")

        if mode == "korail":
            ktrains = Korail(id, pw, auto_login=True)
        elif mode == "srt":
            ktrains = SRT(id, pw, auto_login=True)
        else:
            raise ValueError(f"Invalid mode: {mode}. Must be one of korail or srt.")

        # comma separated list of train numbers
        train_nos = train_nos.split(",")
        email_receivers = email_receivers.split(",")

        train_availability = {train_no: False for train_no in train_nos}

        tickets_reserved = 0
        total_tries = 0
        started = False

        while True:
            try:
                trains = ktrains.search_train(dep, arr, date, time, available_only=False)
    
                # Filter out trains that are not in train_codes
                trains = [train for train in trains if train.train_number in train_nos]
    
                if not started:
                    manage_start(
                        trains, email_sender, email_receivers, email_password, notify, mode
                    )
                    started = True
    
                for train in trains:
                    was_available = train_availability[train.train_number]
                    seat = None
                    ReserveOption = (
                        ReserveOptionKorail if mode == "korail" else ReserveOptionSRT
                    )
                    if seat_type == "R" and train.general_seat_available():
                        seat = ReserveOption.GENERAL_ONLY
                    elif seat_type == "S" and train.special_seat_available():
                        seat = ReserveOption.SPECIAL_ONLY
                    elif seat_type == "B" and train.seat_available():
                        seat = ReserveOption.GENERAL_FIRST
                    else:
                        seat = None
                    if not was_available and seat != None:
                        if reserve:
                            if mode == "korail":
                                ktrains.reserve(train, option=seat)
                            elif mode == "srt":
                                ktrains.reserve(train, special_seat=seat)
                            manage_reservation(
                                train,
                                email_sender,
                                email_receivers,
                                email_password,
                                notify,
                                mode,
                            )
                            print("Reserved 1 ticket!")
                            tickets_reserved += 1
                            if tickets_reserved >= number_of_tickets:
                                print("Reserved all tickets. Exiting...")
                                return
                        else:
                            manage_available(
                                train, email_sender, email_receivers, email_password, notify
                            )
                        train_availability[train.train_number] = True
    
                    elif was_available and not train.seat_available():
                        manage_unavailable(
                            train, email_sender, email_receivers, email_password, notify
                        )
                        train_availability[train.train_number] = False
                        total_tries += 1
                        if total_tries >= number_of_tries:
                            print(f"Max tries reached: {number_of_tries}. Exiting...")
                            return
                    else:
                        pass  # do nothing
            except SRTResponseError as e:
                if "사용자가 많아 접속이" not in str(e):
                    raise e

            # sleep for timeout seconds
            python_time.sleep(timeout)

    except Exception:
        e = traceback.format_exc()
        print("Error:\n" + str(e))
        manage_error(e, email_sender, email_receivers, email_password, notify)
        save_to_log("Error:\n" + str(e))
        chime.error()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", type=str, required=True)
    parser.add_argument("--pw", type=str, required=True)
    parser.add_argument("--email-receivers", type=str, required=True)
    parser.add_argument("--dep", type=str, required=True)
    parser.add_argument("--arr", type=str, required=True)
    parser.add_argument("--date", type=str, required=True)
    parser.add_argument("--time", type=str, required=True)
    parser.add_argument("--train-nos", type=str, required=True)
    parser.add_argument("--mode", type=str, default="korail")
    parser.add_argument("--notify", type=str, default="True")
    parser.add_argument("--reserve", type=str, default="False")
    parser.add_argument("--number-of-tickets", type=int, default=1)
    parser.add_argument("--number-of-tries", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=5)
    parser.add_argument("--email-sender", type=str, default=None)
    parser.add_argument("--email-password", type=str, default=None)
    parser.add_argument("--seat-type", type=str, default="B")
    args = parser.parse_args()

    print(args)
    print(vars(args))
    get_trains(**vars(args))
