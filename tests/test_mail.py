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


def test_the_note_goes_to_the_address_set_for_it():
    calls = []
    env = {"ECRIVEZ_MAIL_TO": "ailleurs@example.org"}
    mail.send("n", env, lambda argv, stdin: calls.append(argv) or "")
    argv = calls[0]
    assert argv[argv.index("--email-receiver") + 1] == "ailleurs@example.org"


def test_without_an_address_the_mail_command_keeps_its_own_default():
    calls = []
    mail.send("n", {}, lambda argv, stdin: calls.append(argv) or "")
    assert "--email-receiver" not in calls[0]


def test_an_address_chosen_for_one_note_wins_over_the_one_set_for_all():
    calls = []
    env = {"ECRIVEZ_MAIL_TO": "ailleurs@example.org"}
    mail.send("n", env, lambda argv, stdin: calls.append(argv) or "", to="hopital@example.org")
    argv = calls[0]
    assert argv[argv.index("--email-receiver") + 1] == "hopital@example.org"


def test_addresses_offered_on_the_page_come_from_the_environment():
    env = {"ECRIVEZ_MAIL_CHOICES": " hopital@example.org , pas une adresse,,b@example.org"}
    assert mail.choices(env) == ["hopital@example.org", "b@example.org"]
    assert mail.choices({}) == []


def test_an_address_can_never_pass_for_an_option_of_the_mail_command():
    assert mail.valid("prenom.nom@chu-exemple.fr")
    for bad in ("-x@example.org", "a b@example.org", "a@b", "a@example.org,b@example.org", ""):
        assert not mail.valid(bad)
