from marula_data_platform.cli import main


def test_main_prints_ready_message(capsys) -> None:
    main()

    captured = capsys.readouterr()
    assert captured.out == "Marula Data Platform is ready.\n"
