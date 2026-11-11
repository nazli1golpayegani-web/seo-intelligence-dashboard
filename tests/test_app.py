from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

PAGES=['SEO Overview','Organic Traffic Analytics','Keyword Intelligence','Landing Page Performance',
'SEO Opportunity Finder','Content Decay & Traffic Loss','SEO Cannibalization Analysis','Technical SEO & Indexing',
'GA4 Business Performance','AI SEO Recommendations','Executive Reports','Connections & Settings']

@pytest.mark.parametrize('page',PAGES)
def test_demo_pages(page,tmp_path,monkeypatch):
    monkeypatch.setenv('SEO_DATA_DIR',str(tmp_path))
    app=AppTest.from_file(str(Path(__file__).parents[1]/'app.py'),default_timeout=40).run()
    assert not app.exception
    app.sidebar.radio[0].set_value(page).run()
    assert not app.exception
    assert app.title[0].value==page
