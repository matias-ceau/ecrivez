from ecrivez import mail


def test_note_goes_to_the_mail_command_with_a_subject_free_of_patient_data():
    calls = []
    mail.send("Mme X, anorexie", {}, lambda argv, stdin: calls.append(argv) or "")
    (argv,) = calls
    assert argv[0] == "send_email.py"
    assert argv[argv.index("-c") + 1] == "Mme X, anorexie"
    subject = argv[argv.index("-s") + 1]
    assert subject.startswith("Note ecrivez 20") and "X" not in subject


def test_mail_command_can_be_replaced():
    calls = []
    mail.send("n", {"ECRIVEZ_MAIL_COMMAND": "autre"}, lambda argv, stdin: calls.append(argv) or "")
    assert calls[0][0] == "autre"


def test_mail_is_unavailable_where_the_command_is_not_installed():
    assert mail.available({"ECRIVEZ_MAIL_COMMAND": "commande-qui-n-existe-pas"}) is False
    assert mail.available({"ECRIVEZ_MAIL_COMMAND": "sh"}) is True
