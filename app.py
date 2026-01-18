from flask import Flask, render_template, request, jsonify
import pdfplumber
import re
import io

app = Flask(__name__)

# Material weight database (lbs per unit)
# Common construction materials with typical weights
MATERIAL_WEIGHTS = {
    # Roofing materials (per SF or per unit)
    'shingle': {'weight': 2.5, 'unit': 'SF', 'description': 'Asphalt shingles'},
    '3-tab shingle': {'weight': 2.2, 'unit': 'SF', 'description': '3-tab asphalt shingles'},
    'architectural shingle': {'weight': 3.0, 'unit': 'SF', 'description': 'Architectural/dimensional shingles'},
    'laminated shingle': {'weight': 3.0, 'unit': 'SF', 'description': 'Laminated shingles'},
    'felt': {'weight': 0.1, 'unit': 'SF', 'description': 'Roofing felt/underlayment'},
    'underlayment': {'weight': 0.15, 'unit': 'SF', 'description': 'Synthetic underlayment'},
    'ice & water': {'weight': 0.25, 'unit': 'SF', 'description': 'Ice and water shield'},
    'ice and water': {'weight': 0.25, 'unit': 'SF', 'description': 'Ice and water shield'},
    'flashing': {'weight': 0.5, 'unit': 'LF', 'description': 'Metal flashing'},
    'drip edge': {'weight': 0.3, 'unit': 'LF', 'description': 'Drip edge'},
    'ridge cap': {'weight': 0.4, 'unit': 'LF', 'description': 'Ridge cap shingles'},
    'ridge vent': {'weight': 0.5, 'unit': 'LF', 'description': 'Ridge vent'},
    'vent': {'weight': 3.0, 'unit': 'EA', 'description': 'Roof vent'},
    'plywood': {'weight': 1.8, 'unit': 'SF', 'description': 'Plywood sheathing'},
    'osb': {'weight': 1.7, 'unit': 'SF', 'description': 'OSB sheathing'},
    'decking': {'weight': 1.8, 'unit': 'SF', 'description': 'Roof decking'},
    'sheathing': {'weight': 1.8, 'unit': 'SF', 'description': 'Roof sheathing'},
    'tile': {'weight': 9.5, 'unit': 'SF', 'description': 'Roof tile'},
    'metal roof': {'weight': 1.5, 'unit': 'SF', 'description': 'Metal roofing'},
    'slate': {'weight': 15.0, 'unit': 'SF', 'description': 'Slate roofing'},
    'wood shake': {'weight': 3.5, 'unit': 'SF', 'description': 'Wood shake'},
    'cedar shake': {'weight': 3.5, 'unit': 'SF', 'description': 'Cedar shake'},
    
    # Siding materials
    'siding': {'weight': 1.2, 'unit': 'SF', 'description': 'Vinyl siding'},
    'vinyl siding': {'weight': 1.0, 'unit': 'SF', 'description': 'Vinyl siding'},
    'wood siding': {'weight': 2.5, 'unit': 'SF', 'description': 'Wood siding'},
    'fiber cement': {'weight': 2.3, 'unit': 'SF', 'description': 'Fiber cement siding'},
    'hardie': {'weight': 2.3, 'unit': 'SF', 'description': 'Hardie board siding'},
    'aluminum siding': {'weight': 0.8, 'unit': 'SF', 'description': 'Aluminum siding'},
    'stucco': {'weight': 10.0, 'unit': 'SF', 'description': 'Stucco'},
    'brick': {'weight': 40.0, 'unit': 'SF', 'description': 'Brick veneer'},
    'stone': {'weight': 25.0, 'unit': 'SF', 'description': 'Stone veneer'},
    
    # Gutters
    'gutter': {'weight': 0.8, 'unit': 'LF', 'description': 'Gutters'},
    'downspout': {'weight': 0.5, 'unit': 'LF', 'description': 'Downspouts'},
    
    # Drywall/Interior
    'drywall': {'weight': 1.8, 'unit': 'SF', 'description': 'Drywall'},
    'sheetrock': {'weight': 1.8, 'unit': 'SF', 'description': 'Sheetrock'},
    'plaster': {'weight': 5.0, 'unit': 'SF', 'description': 'Plaster'},
    'paneling': {'weight': 1.5, 'unit': 'SF', 'description': 'Wall paneling'},
    'insulation': {'weight': 0.1, 'unit': 'SF', 'description': 'Insulation'},
    'batt insulation': {'weight': 0.1, 'unit': 'SF', 'description': 'Batt insulation'},
    'blown insulation': {'weight': 0.05, 'unit': 'SF', 'description': 'Blown insulation'},
    
    # Flooring
    'carpet': {'weight': 0.5, 'unit': 'SF', 'description': 'Carpet'},
    'pad': {'weight': 0.2, 'unit': 'SF', 'description': 'Carpet pad'},
    'vinyl flooring': {'weight': 0.5, 'unit': 'SF', 'description': 'Vinyl flooring'},
    'lvp': {'weight': 0.5, 'unit': 'SF', 'description': 'Luxury vinyl plank'},
    'laminate flooring': {'weight': 1.0, 'unit': 'SF', 'description': 'Laminate flooring'},
    'hardwood': {'weight': 2.5, 'unit': 'SF', 'description': 'Hardwood flooring'},
    'tile floor': {'weight': 6.0, 'unit': 'SF', 'description': 'Ceramic tile'},
    'ceramic tile': {'weight': 6.0, 'unit': 'SF', 'description': 'Ceramic tile'},
    'porcelain': {'weight': 7.0, 'unit': 'SF', 'description': 'Porcelain tile'},
    'subfloor': {'weight': 1.8, 'unit': 'SF', 'description': 'Subfloor'},
    
    # Windows and doors
    'window': {'weight': 50.0, 'unit': 'EA', 'description': 'Window'},
    'door': {'weight': 60.0, 'unit': 'EA', 'description': 'Door'},
    'screen': {'weight': 5.0, 'unit': 'EA', 'description': 'Screen'},
    'trim': {'weight': 0.3, 'unit': 'LF', 'description': 'Trim'},
    'casing': {'weight': 0.3, 'unit': 'LF', 'description': 'Door/window casing'},
    'baseboard': {'weight': 0.4, 'unit': 'LF', 'description': 'Baseboard'},
    
    # Structural
    'framing': {'weight': 2.0, 'unit': 'LF', 'description': 'Wood framing'},
    'rafter': {'weight': 3.0, 'unit': 'LF', 'description': 'Rafters'},
    'joist': {'weight': 2.5, 'unit': 'LF', 'description': 'Joists'},
    'stud': {'weight': 2.0, 'unit': 'LF', 'description': 'Wall studs'},
    'beam': {'weight': 5.0, 'unit': 'LF', 'description': 'Beams'},
    'fascia': {'weight': 1.5, 'unit': 'LF', 'description': 'Fascia board'},
    'soffit': {'weight': 0.8, 'unit': 'SF', 'description': 'Soffit'},
    
    # Miscellaneous
    'concrete': {'weight': 12.0, 'unit': 'SF', 'description': 'Concrete'},
    'debris': {'weight': 5.0, 'unit': 'SF', 'description': 'General debris'},
    'fence': {'weight': 3.0, 'unit': 'LF', 'description': 'Fence'},
    'deck': {'weight': 3.0, 'unit': 'SF', 'description': 'Deck boards'},
    'cabinet': {'weight': 100.0, 'unit': 'EA', 'description': 'Cabinet'},
    'countertop': {'weight': 15.0, 'unit': 'LF', 'description': 'Countertop'},
    'fixture': {'weight': 30.0, 'unit': 'EA', 'description': 'Fixture'},
    'appliance': {'weight': 150.0, 'unit': 'EA', 'description': 'Appliance'},
}

# Keywords indicating removal/demolition
REMOVAL_KEYWORDS = [
    'tear off', 'tearoff', 'tear-off',
    'remove', 'removal',
    'demo', 'demolish', 'demolition',
    'strip', 'rip out', 'rip-out',
    'dispose', 'disposal',
    'haul', 'hauling',
    'detach', 'take out',
    'r&r',  # Remove and Replace
    'pull',
]


def is_removal_item(description):
    """Check if line item is a removal/demolition item."""
    desc_lower = description.lower()
    for keyword in REMOVAL_KEYWORDS:
        if keyword in desc_lower:
            return True
    return False


def find_material_weight(description):
    """Find material weight from description."""
    desc_lower = description.lower()
    
    # Try to match specific materials first (longer matches)
    best_match = None
    best_match_length = 0
    
    for material, data in MATERIAL_WEIGHTS.items():
        if material in desc_lower:
            if len(material) > best_match_length:
                best_match = data
                best_match_length = len(material)
    
    return best_match


def parse_xactimate_pdf(file_bytes):
    """Parse Xactimate PDF and extract line items."""
    line_items = []
    
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
    
    lines = full_text.split('\n')
    
    # Multiple patterns for different Xactimate formats
    patterns = [
        # Format: 1. Description 100.00 SF 1,234.56
        r'^(\d+)\.\s+(.+?)\s+([\d,]+\.?\d*)\s+(SF|SQ|LF|EA|HR|SY|CF|CY|GAL|LS)\s',
        # Format with line number and code: 1. RFG LABO - Description...
        r'^(\d+)\.\s+([A-Z]{2,6}\s+[A-Z]{2,6}\s*[-–]\s*.+?)\s+([\d,]+\.?\d*)\s+(SF|SQ|LF|EA|HR|SY|CF|CY|GAL|LS)',
        # Format: Description quantity unit (no line number)
        r'^([A-Z][^0-9]{10,}?)\s+([\d,]+\.?\d*)\s+(SF|SQ|LF|EA|HR|SY|CF|CY|GAL|LS)\s',
        # Xactimate code format: RFG LABO Tear off...
        r'^([A-Z]{2,6}\s+[A-Z]{2,6})\s+(.+?)\s+([\d,]+\.?\d*)\s+(SF|SQ|LF|EA|HR|SY|CF|CY|GAL|LS)',
    ]
    
    seen_descriptions = set()
    
    for line in lines:
        line = line.strip()
        if not line or len(line) < 10:
            continue
        
        # Skip header/footer lines
        if any(skip in line.lower() for skip in ['page ', 'total', 'subtotal', 'grand total', 'claim #', 'date of loss']):
            continue
            
        for pattern in patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                try:
                    groups = match.groups()
                    
                    if len(groups) == 4:
                        # Pattern with line number
                        if groups[0].isdigit():
                            line_number = groups[0]
                            description = groups[1].strip()
                            quantity_str = groups[2]
                            unit = groups[3].upper()
                        else:
                            line_number = '?'
                            description = (groups[0] + ' ' + groups[1]).strip()
                            quantity_str = groups[2]
                            unit = groups[3].upper()
                    else:
                        line_number = '?'
                        description = groups[0].strip()
                        quantity_str = groups[1]
                        unit = groups[2].upper()
                    
                    quantity = float(quantity_str.replace(',', ''))
                    
                    # Skip if we've seen this exact description (avoid duplicates)
                    desc_key = description.lower()[:50]
                    if desc_key in seen_descriptions:
                        continue
                    seen_descriptions.add(desc_key)
                    
                    if quantity > 0 and len(description) > 3:
                        line_items.append({
                            'line_number': line_number,
                            'description': description,
                            'quantity': quantity,
                            'unit': unit,
                            'is_removal': is_removal_item(description)
                        })
                except (ValueError, IndexError):
                    continue
                break
    
    # Secondary pass: look for removal-related lines we might have missed
    for line in lines:
        line_lower = line.lower()
        if any(kw in line_lower for kw in REMOVAL_KEYWORDS):
            # Check if we already captured this
            already_found = any(item['description'].lower()[:30] in line_lower for item in line_items)
            if already_found:
                continue
                
            # Try to extract quantity and unit
            qty_match = re.search(r'([\d,]+\.?\d+)\s*(SF|SQ|LF|EA|HR|SY)', line, re.IGNORECASE)
            if qty_match:
                try:
                    quantity = float(qty_match.group(1).replace(',', ''))
                    unit = qty_match.group(2).upper()
                    
                    # Extract a reasonable description
                    desc = line[:100].strip()
                    
                    if quantity > 0:
                        line_items.append({
                            'line_number': '?',
                            'description': desc,
                            'quantity': quantity,
                            'unit': unit,
                            'is_removal': True
                        })
                except ValueError:
                    pass
    
    return line_items, full_text


def calculate_waste_weight(line_items):
    """Calculate total waste weight from removal items."""
    waste_items = []
    total_weight = 0
    unmatched_items = []
    
    for item in line_items:
        if not item['is_removal']:
            continue
        
        material_data = find_material_weight(item['description'])
        
        if material_data:
            # Calculate weight
            weight = item['quantity'] * material_data['weight']
            total_weight += weight
            
            waste_items.append({
                'description': item['description'],
                'quantity': item['quantity'],
                'unit': item['unit'],
                'material_type': material_data['description'],
                'weight_per_unit': material_data['weight'],
                'total_weight': weight
            })
        else:
            # Unmatched item - use default estimate
            default_weight = 2.0  # lbs per unit
            weight = item['quantity'] * default_weight
            total_weight += weight
            
            unmatched_items.append({
                'description': item['description'],
                'quantity': item['quantity'],
                'unit': item['unit'],
                'estimated_weight': weight
            })
    
    return {
        'waste_items': waste_items,
        'unmatched_items': unmatched_items,
        'total_weight_lbs': total_weight,
        'total_weight_tons': total_weight / 2000
    }


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'File must be a PDF'}), 400
    
    try:
        file_bytes = file.read()
        line_items, raw_text = parse_xactimate_pdf(file_bytes)
        
        waste_data = calculate_waste_weight(line_items)
        
        return jsonify({
            'success': True,
            'filename': file.filename,
            'total_line_items': len(line_items),
            'removal_items_found': len([i for i in line_items if i['is_removal']]),
            'waste_summary': waste_data,
            'all_line_items': line_items,
            'raw_text_preview': raw_text[:5000] if raw_text else 'No text extracted'
        })
        
    except Exception as e:
        import traceback
        return jsonify({'error': f'Error processing PDF: {str(e)}', 'trace': traceback.format_exc()}), 500


@app.route('/debug', methods=['POST'])
def debug_pdf():
    """Debug endpoint to see raw PDF text extraction."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    file_bytes = file.read()
    
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        pages_text = []
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            pages_text.append({
                'page': i + 1,
                'text': text if text else 'No text extracted'
            })
    
    return jsonify({'pages': pages_text})


if __name__ == '__main__':
    app.run(debug=True, port=5000)
