/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";

export class SalesKPI extends Component {
    setup() {
        this.state = useState({
            kpi: this.props.kpi || {},
            isAnimating: false,
            visibleCards: [],
        });

        onMounted(() => {
            this._animateKPICards();
        });
    }

    _animateKPICards() {
        this.state.isAnimating = true;
        const cards = document.querySelectorAll(".kpi-card");

        cards.forEach((card, index) => {
            setTimeout(() => {
                card.classList.add("animate-in");
                this.state.visibleCards.push(index);
            }, index * 150);
        });
    }

    setKPI(kpi) {
        this.state.kpi = kpi;
        this._animateKPICards();
    }

    formatCurrency(value) {
        return new Intl.NumberFormat("id-ID", {
            style: "currency",
            currency: "IDR",
            minimumFractionDigits: 0,
            maximumFractionDigits: 0,
        }).format(value || 0);
    }

    formatNumber(value) {
        return new Intl.NumberFormat("id-ID").format(value || 0);
    }

    getCardIcon(type) {
        const icons = {
            total_revenue: "💰",
            total_orders: "📦",
            total_customers: "👥",
            total_products: "🏷️",
            total_qty: "📊",
            avg_order_value: "📈",
            total_margin: "💹",
        };
        return icons[type] || "📈";
    }

    getCardColor(type) {
        const colors = {
            total_revenue: "from-purple-500 to-indigo-600",
            total_orders: "from-green-500 to-emerald-600",
            total_customers: "from-blue-500 to-cyan-600",
            total_products: "from-orange-500 to-amber-600",
            total_qty: "from-pink-500 to-rose-600",
            avg_order_value: "from-yellow-500 to-orange-600",
            total_margin: "from-teal-500 to-emerald-600",
        };
        return colors[type] || "from-gray-500 to-gray-600";
    }
}

SalesKPI.template = "sales_analytics_dashboard.kpi_template";
