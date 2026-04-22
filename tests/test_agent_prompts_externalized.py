from pathlib import Path


def test_producer_uses_markdown_prompt_file():
    producer_source = Path("src/ll_video_maker/producer.py").read_text(encoding="utf-8")
    assert 'render_prompt("producer")' in producer_source
    assert 'PRODUCER_PROMPT = """' not in producer_source
