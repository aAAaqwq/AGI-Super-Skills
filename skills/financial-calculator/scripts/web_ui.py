#!/usr/bin/env python3
"""
Financial Calculator - Web UI Server
Launch with: python3 web_ui.py [port]
"""

from flask import Flask, render_template, request, jsonify
import os
import sys

# Add scripts directory to path to import calculate module
sys.path.insert(0, os.path.dirname(__file__))
import calculate

app = Flask(__name__, 
            template_folder='../assets',
            static_folder='../assets')


@app.route('/')
def index():
    """Serve the main calculator page"""
    return render_template('calculator.html')


@app.route('/api/future-value', methods=['POST'])
def api_future_value():
    """Calculate future value"""
    data = request.json
    try:
        result = calculate.future_value(
            present_value=float(data['principal']),
            rate=float(data['rate']) / 100,  # Convert percentage to decimal
            periods=int(data['years']),
            compound_frequency=int(data.get('frequency', 1))
        )
        return jsonify({'success': True, 'future_value': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/present-value', methods=['POST'])
def api_present_value():
    """Calculate present value"""
    data = request.json
    try:
        result = calculate.present_value(
            future_value=float(data['future_value']),
            rate=float(data['rate']) / 100,
            periods=int(data['years']),
            compound_frequency=int(data.get('frequency', 1))
        )
        return jsonify({'success': True, 'present_value': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/discount', methods=['POST'])
def api_discount():
    """Calculate discount"""
    data = request.json
    try:
        result = calculate.discount_amount(
            original_price=float(data['price']),
            discount_percent=float(data['discount'])
        )
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/markup', methods=['POST'])
def api_markup():
    """Calculate markup"""
    data = request.json
    try:
        result = calculate.markup_price(
            cost=float(data['cost']),
            markup_percent=float(data['markup'])
        )
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/compound-interest', methods=['POST'])
def api_compound_interest():
    """Calculate compound interest details"""
    data = request.json
    try:
        result = calculate.compound_interest(
            principal=float(data['principal']),
            rate=float(data['rate']) / 100,
            periods=int(data['years']),
            compound_frequency=int(data.get('frequency', 1))
        )
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/fv-table', methods=['POST'])
def api_fv_table():
    """Generate future value table"""
    data = request.json
    try:
        rates = [float(r) / 100 for r in data['rates']]  # Convert to decimals
        periods = [int(p) for p in data['periods']]
        
        result = calculate.generate_fv_table(
            principal=float(data['principal']),
            rates=rates,
            periods=periods
        )
        return jsonify({'success': True, 'table': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/discount-table', methods=['POST'])
def api_discount_table():
    """Generate discount table"""
    data = request.json
    try:
        discounts = [float(d) for d in data['discounts']]
        
        result = calculate.generate_discount_table(
            original_price=float(data['price']),
            discounts=discounts
        )
        return jsonify({'success': True, 'table': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/growth-timeline', methods=['POST'])
def api_growth_timeline():
    """Generate year-by-year growth timeline"""
    data = request.json
    try:
        principal = float(data['principal'])
        rate = float(data['rate']) / 100
        years = float(data['years'])
        frequency = int(data.get('frequency', 1))
        
        timeline = []
        total_interest = 0
        
        # Generate timeline for each year
        num_years = int(years) + 1
        for year in range(num_years):
            if year == 0:
                balance = principal
                interest = 0
            else:
                balance = calculate.future_value(principal, rate, year, frequency)
                prev_balance = calculate.future_value(principal, rate, year - 1, frequency) if year > 1 else principal
                interest = balance - prev_balance
                total_interest += interest
            
            timeline.append({
                'year': year,
                'balance': round(balance, 2),
                'interest': round(interest, 2),
                'total_interest': round(total_interest, 2)
            })
        
        return jsonify({'success': True, 'timeline': timeline})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/multi-growth', methods=['POST'])
def api_multi_growth():
    """Generate multi-rate growth comparison"""
    data = request.json
    try:
        principal = float(data['principal'])
        rates = [float(r) / 100 for r in data['rates']]
        years = int(data['years'])
        frequency = int(data.get('frequency', 1))
        
        series = []
        for rate in rates:
            values = []
            for year in range(years + 1):
                if year == 0:
                    value = principal
                else:
                    value = calculate.future_value(principal, rate, year, frequency)
                values.append(round(value, 2))
            
            series.append({
                'rate': rate * 100,
                'values': values
            })
        
        return jsonify({'success': True, 'series': series})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5050
    print(f"\n🧮 Financial Calculator")
    print(f"📊 Open: http://localhost:{port}")
    print(f"Press Ctrl+C to stop\n")
    app.run(host='0.0.0.0', port=port, debug=False)
