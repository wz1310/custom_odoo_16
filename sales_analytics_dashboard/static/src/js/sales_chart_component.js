/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";

export class SalesChart extends Component {
    setup() {
        this.state = useState({
            chartData: this.props.data || {},
            trends: this.props.trends || {},
            isLoading: false,
            selectedPeriod: "monthly",
            chartHeight: 300,
        });

        onMounted(() => {
            this._calculateChartHeight();
            this._renderCharts();
        });
    }

    _calculateChartHeight() {
        const container = document.querySelector(".sales-chart-container");
        if (container) {
            this.state.chartHeight = Math.max(200, window.innerHeight * 0.3);
        }
    }

    _renderCharts() {
        this._renderTrendChart();
        this._renderCategoryChart();
        this._renderTopProductsChart();
    }

    _renderTrendChart() {
        const trends = this.state.trends;
        const bars = document.querySelectorAll(".trend-bar");
        
        if (Object.keys(trends).length === 0) return;

        const values = Object.values(trends).map((t) => t.revenue);
        const maxVal = Math.max(...values, 1);

        bars.forEach((bar, index) => {
            const value = values[index] || 0;
            const percentage = (value / maxVal) * 100;
            const barInner = bar.querySelector(".trend-bar-inner");
            
            if (barInner) {
                barInner.style.height = "0%";
                setTimeout(() => {
                    barInner.style.height = `${Math.max(percentage, 2)}%`;
                }, index * 100);
            }
        });
    }

    _renderCategoryChart() {
        const categories = this.props.topCategories || [];
        const bars = document.querySelectorAll(".category-bar");

        if (categories.length === 0) return;

        const maxVal = Math.max(...categories.map((c) => c[1]), 1);

        bars.forEach((bar, index) => {
            const category = categories[index];
            if (!category) return;

            const percentage = (category[1] / maxVal) * 100;
            const barInner = bar.querySelector(".category-bar-inner");

            if (barInner) {
                barInner.style.width = "0%";
                setTimeout(() => {
                    barInner.style.width = `${Math.max(percentage, 2)}%`;
                }, 200 + index * 150);
            }
        });
    }

    _renderTopProductsChart() {
        const products = this.props.topProducts || [];
        const bars = document.querySelectorAll(".product-bar");

        if (products.length === 0) return;

        const maxVal = Math.max(...products.map((p) => p[1]), 1);

        bars.forEach((bar, index) => {
            const product = products[index];
            if (!product) return;

            const percentage = (product[1] / maxVal) * 100;
            const barInner = bar.querySelector(".product-bar-inner");

            if (barInner) {
                barInner.style.width = "0%";
                setTimeout(() => {
                    barInner.style.width = `${Math.max(percentage, 2)}%`;
                }, 300 + index * 150);
            }
        });
    }

    setTrends(trends) {
        this.state.trends = trends;
        this._renderTrendChart();
    }

    setTopCategories(categories) {
        this.props.topCategories = categories;
        this._renderCategoryChart();
    }

    setTopProducts(products) {
        this.props.topProducts = products;
        this._renderTopProductsChart();
    }

    changePeriod(period) {
        this.state.selectedPeriod = period;
        this._renderCharts();
    }

    formatCurrency(value) {
        return new Intl.NumberFormat("id-ID", {
            style: "currency",
            currency: "IDR",
            minimumFractionDigits: 0,
            maximumFractionDigits: 0,
        }).format(value);
    }
}

SalesChart.template = "sales_analytics_dashboard.chart_template";
