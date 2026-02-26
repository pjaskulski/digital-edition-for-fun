""" Prosta edycja cyfrowa """
import re
import math
import copy
import urllib.parse
from flask import Flask, render_template, request, abort
from bs4 import BeautifulSoup


app = Flask(__name__)


# -------------------------------- FUNCTIONS ----------------------------------
def xml_to_html(xml_node, soup):
    """ zmiana tagów TEI na formatowanie HTML """
    if not xml_node: return ""
    node = copy.copy(xml_node) 
    
    for tag in node.find_all('persName'):
        new_tag = soup.new_tag('a', href=tag.get('ref', '#'), title=tag.get('key', ''), target="_blank", **{'class': 'badge bg-primary text-decoration-none'})
        new_tag.string = tag.text
        tag.replace_with(new_tag)
        
    for tag in node.find_all('placeName'):
        new_tag = soup.new_tag('a', href=tag.get('ref', '#'), title=tag.get('key', ''), target="_blank", **{'class': 'badge bg-success text-decoration-none'})
        new_tag.string = tag.text
        tag.replace_with(new_tag)
        
    # przypisy (<note>)
    for tag in node.find_all('note'):
        note_text = re.sub(r'\s+', ' ', tag.get_text()).strip()
        note_number = tag.get('n', '*')
        
        # interaktywny link, który uruchomi dymek popover
        new_tag = soup.new_tag('a', 
                               tabindex="0", 
                               role="button", 
                               **{
                                   'class': 'text-danger text-decoration-none fw-bold mx-1',
                                   'data-bs-toggle': 'popover',
                                   'data-bs-trigger': 'focus', # zamykanie dymku po kliknięciu gdzie indziej
                                   'data-bs-placement': 'top',
                                   'data-bs-content': note_text,
                                   'title': f"Przypis {note_number}"
                               })
        
        # górny indeks (sup) wewnątrz linku
        sup_tag = soup.new_tag('sup')
        sup_tag.string = f"[{note_number}]"
        new_tag.append(sup_tag)
        
        tag.replace_with(new_tag)

    # znaczniki nowej strony (<pb>)
    for pb in node.find_all('pb'):
        page_num = pb.get('n')
        if page_num:
            # znacznik numeru strony
            new_tag = soup.new_tag('span', **{'class': 'small text-black-50 fw-bold user-select-none'})
            new_tag.string = f" [str. {page_num}] "
            pb.replace_with(new_tag)
        else:
            pb.decompose()

    # obsługa nagłówków z nr strony, numerami dokumentów na stronie i rokiem dokumemtów (<fw type="header">)
    for fw in node.find_all('fw', type='header'):
        new_tag = soup.new_tag('span', **{
            'class': 'd-block small text-muted border-top border-secondary-subtle pt-1 mt-3 mb-2 text-end fst-italic user-select-none'
        })
        new_tag.string = fw.text
        fw.replace_with(new_tag)
        
    return "".join(str(c) for c in node.contents)


def load_data(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'xml')

    documents = []
    persons_set = set()
    places_set = set()
    person_index = {} # słownik na indeks osób
    place_index = {}  # słownik na indeks miejsc

    for div in soup.find_all('div', type='document'):
        doc_id = div.get('n')
        title = div.find('head').get_text(strip=True) if div.find('head') else f"Dokument {doc_id}"

        date_place_node = div.find('ab', type='date-place')
        if date_place_node:
            # Wersja HTML z kolorowymi tagami do doc.html
            date_place_html = re.sub(r'\s+', ' ', xml_to_html(date_place_node, soup)).strip()
            
            # Wersja czysto tekstowa do index.html
            date_place_plain = re.sub(r'\s+', ' ', date_place_node.get_text()).strip()
        else:
            date_place_html = ""
            date_place_plain = ""

        summary_node = div.find('ab', type='summary')
        
        if summary_node:
            # wersja HTML z dymkami i tagami dla widoku dokumentu (doc.html)
            summary_html = xml_to_html(summary_node, soup)
            
            # wersja czysto tekstowa na stronę główną (index.html)
            summary_clean = copy.copy(summary_node)
            # usuwanie przypisu z wersji czysto tekstowej, aby ich treść nie wkleiła się w zdanie
            for note in summary_clean.find_all('note'):
                note.decompose() 
                
            summary_plain = re.sub(r'\s+', ' ', summary_clean.get_text()).strip()
            
            # skracanie do 60 słów
            words = summary_plain.split()
            if len(words) > 60:
                summary_short = " ".join(words[:60]) + "..."
            else:
                summary_short = summary_plain
        else:
            summary_html = ""
            summary_short = ""

        source_node = div.find('ab', type='source')
        source_html = xml_to_html(source_node, soup) if source_node else ""

        # unikalne klucze do filtrowania i zbieranie danych do indeksu
        for p in div.find_all('persName'):
            key = p.get('key')
            ref = p.get('ref', '')
            if key: 
                persons_set.add(key)
                if key not in person_index:
                    person_index[key] = {'ref': ref, 'docs': {}}
                person_index[key]['docs'][doc_id] = title

        for p in div.find_all('placeName'):
            key = p.get('key')
            ref = p.get('ref', '')
            if key: 
                places_set.add(key)
                if key not in place_index:
                    place_index[key] = {'ref': ref, 'docs': {}}
                place_index[key]['docs'][doc_id] = title

        orig_div = div.find('div', type='original')
        trans_div = div.find('div', type='translation')

        documents.append({
            'id': doc_id,
            'title': title,
            'date_place_html': date_place_html,
            'date_place_plain': date_place_plain,
            'summary_short': summary_short, 
            'summary_html': summary_html, 
            'source_html': source_html,
            'original_html': xml_to_html(orig_div, soup),
            'translation_html': xml_to_html(trans_div, soup),
            'search_text': div.get_text().lower() # zwykły tekst małymi literami do wyszukiwarki
        })

    return documents, sorted(list(persons_set)), sorted(list(places_set)), person_index, place_index

# wczytanie "bazy danych" do pamięci przy starcie
DOCS, PERSONS, PLACES, PERSON_INDEX, PLACE_INDEX = load_data('Acta_Alexandri_Regis_Poloniae.xml')


@app.route('/')
def index():
    q = request.args.get('q', '').lower()
    
    # pobieranie listy zaznaczonych wartości, a nie pojedyncze stringi
    person_filters = request.args.getlist('person') 
    place_filters = request.args.getlist('place')   
    
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1

    # logika filtrowania fasetowego
    results = DOCS
    if q:
        results = [d for d in results if q in d['search_text']]
        
    if person_filters:
        # dokument musi zawierać wszystkie z zaznaczonych osób (logika AND)
        results = [d for d in results if all(p in d['original_html'] or p in d['translation_html'] for p in person_filters)]
        
    if place_filters:
        # dokument musi zawierać wszystkie z zaznaczonych miejsc (logika AND)
        results = [d for d in results if all(p in d['original_html'] or p in d['translation_html'] for p in place_filters)]

    # logika paginacji
    per_page = 10 
    total_results = len(results)
    total_pages = math.ceil(total_results / per_page)
    
    if page < 1: page = 1
    if page > total_pages and total_pages > 0: page = total_pages

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_results = results[start_idx:end_idx]

    # generowanie listy stron z wielokropkamido paginacji na dole
    iter_pages = []
    if total_pages <= 7:
        # Jeśli stron jest mało (do 7), wyświetlamy wszystkie
        iter_pages = list(range(1, total_pages + 1))
    else:
        # Jeśli jesteśmy blisko początku
        if page <= 4:
            iter_pages = [1, 2, 3, 4, 5, None, total_pages]
        # Jeśli jesteśmy blisko końca
        elif page >= total_pages - 3:
            iter_pages = [1, None, total_pages - 4, total_pages - 3, total_pages - 2, total_pages - 1, total_pages]
        # Jeśli jesteśmy w środku
        else:
            iter_pages = [1, None, page - 1, page, page + 1, None, total_pages]

    # generowanie bazowego linku dla paginacji (aby nie zgubić wielu zaznaczonych checkboxów)
    query_dict = [('q', q)]
    for p in person_filters: query_dict.append(('person', p))
    for p in place_filters: query_dict.append(('place', p))
    base_query = urllib.parse.urlencode(query_dict)

    return render_template('index.html', 
                           docs=paginated_results, 
                           persons=PERSONS, 
                           places=PLACES, 
                           q=q, 
                           sel_persons=person_filters,
                           sel_places=place_filters, 
                           page=page,
                           total_pages=total_pages,
                           total_results=total_results,
                           base_query=base_query,
                           iter_pages=iter_pages)      


@app.route('/doc/<doc_id>')
def document(doc_id):
    doc = next((d for d in DOCS if d['id'] == doc_id), None)

    # jeśli nie znaleziono dokumentu, rzuć błędem 404
    if doc is None:
        abort(404)

    return render_template('doc.html', doc=doc)


@app.route('/indeks')
def index_entities():
    # sortowanie alfabetyczne
    sorted_persons = dict(sorted(PERSON_INDEX.items()))
    sorted_places = dict(sorted(PLACE_INDEX.items()))
    
    return render_template('indeks.html', persons=sorted_persons, places=sorted_places)


@app.errorhandler(404)
def page_not_found(e):
    # szablon oraz kod błędu 404
    return render_template('404.html'), 404

# -------------------------------- MAIN ---------------------------------------
if __name__ == '__main__':
    app.run(debug=False)
