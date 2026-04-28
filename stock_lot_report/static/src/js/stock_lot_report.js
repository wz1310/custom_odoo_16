/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
const { Component, onWillStart, useState, markup } = owl;

const STORAGE_KEY1 = "slr_group_by";
const STORAGE_KEY2 = "slr_group_by2";

export class StockLotReport extends Component {
    setup() {
        this.rpc = useService("rpc");
        this.state = useState({
            html_content: "",
            loading: true,
            check_date: "",
            group_by: localStorage.getItem(STORAGE_KEY1) || "",
            group_by2: localStorage.getItem(STORAGE_KEY2) || "",
            groupDropdownOpen: false,
            date_label: "Stok Saat Ini",
        });

        this.groupOptions = [
            { value: "location", label: "Lokasi" },
            { value: "product", label: "Produk" },
        ];

        onWillStart(async () => {
            await this.fetchReport();
        });
    }

    groupLabel(val) {
        return val === "location" ? "Lokasi" : val === "product" ? "Produk" : val;
    }

    isGroupSelected(val) {
        return this.state.group_by === val || this.state.group_by2 === val;
    }

    getGroupLevel(val) {
        if (this.state.group_by === val) return 1;
        if (this.state.group_by2 === val) return 2;
        return "";
    }

    toggleGroupDropdown(ev) {
        ev.stopPropagation();
        this.state.groupDropdownOpen = !this.state.groupDropdownOpen;
    }

    selectGroup(val) {
        if (this.state.group_by === val) {
            // Deselect L1 → clear both
            this.state.group_by = "";
            this.state.group_by2 = "";
            localStorage.removeItem(STORAGE_KEY1);
            localStorage.removeItem(STORAGE_KEY2);
        } else if (this.state.group_by2 === val) {
            // Deselect L2
            this.state.group_by2 = "";
            localStorage.removeItem(STORAGE_KEY2);
        } else if (!this.state.group_by) {
            // Set L1
            this.state.group_by = val;
            localStorage.setItem(STORAGE_KEY1, val);
        } else if (!this.state.group_by2) {
            // Set L2 (tidak boleh sama dengan L1)
            if (val !== this.state.group_by) {
                this.state.group_by2 = val;
                localStorage.setItem(STORAGE_KEY2, val);
            }
        }
        this.state.groupDropdownOpen = false;
    }

    removeGroup(level) {
        if (level === 1) {
            this.state.group_by = "";
            this.state.group_by2 = "";
            localStorage.removeItem(STORAGE_KEY1);
            localStorage.removeItem(STORAGE_KEY2);
        } else {
            this.state.group_by2 = "";
            localStorage.removeItem(STORAGE_KEY2);
        }
        this.fetchReport();
    }

    onDateChange(ev) {
        this.state.check_date = ev.target.value;
    }

    applyFilter() {
        this.state.groupDropdownOpen = false;
        this._updateDateLabel();
        this.fetchReport();
    }

    _updateDateLabel() {
        if (this.state.check_date) {
            const d = new Date(this.state.check_date);
            const months = ["Jan","Feb","Mar","Apr","Mei","Jun","Jul","Agu","Sep","Okt","Nov","Des"];
            this.state.date_label = `Per Tanggal: ${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`;
        } else {
            this.state.date_label = "Stok Saat Ini";
        }
    }

    _getActiveCompanyIds() {
        const urlParams = new URLSearchParams(window.location.search);
        const cids = urlParams.get("cids");
        if (cids) return cids.split(",").map(Number).filter(Boolean);
        const cookieMatch = document.cookie.match(/(?:^|;\s*)cids=([^;]*)/);
        if (cookieMatch) return cookieMatch[1].split(",").map(Number).filter(Boolean);
        return [];
    }

    async fetchReport() {
        this.state.loading = true;
        try {
            const company_ids = this._getActiveCompanyIds();
            const data = await this.rpc("/stock_lot_report/data", {
                check_date: this.state.check_date || null,
                company_ids: company_ids.length ? company_ids : null,
                group_by: this.state.group_by || null,
                group_by2: this.state.group_by2 || null,
            });
            this.state.html_content = markup(data);
        } catch (e) {
            console.error("StockLotReport RPC error:", e);
        } finally {
            this.state.loading = false;
        }
    }

    // Handle clicks di area konten (tabel) — fold/unfold
    handleContentClick(ev) {
        const t = ev.target;

        // Tutup dropdown jika klik di luar
        if (this.state.groupDropdownOpen) {
            this.state.groupDropdownOpen = false;
        }

        // Fold level 1
        const l1 = t.closest(".slr-group-l1");
        if (l1) {
            const gid = l1.getAttribute("data-gid");
            const container = ev.currentTarget;
            const folded = l1.classList.contains("folded");
            if (folded) {
                l1.classList.remove("folded");
                container.querySelectorAll(`[data-pgid="${gid}"]`).forEach(el => {
                    el.classList.remove("slr-hidden");
                    if (el.classList.contains("slr-group-l2") && !el.classList.contains("folded")) {
                        const sgid = el.getAttribute("data-gid");
                        container.querySelectorAll(`.slr-group-row[data-gid="${sgid}"]`).forEach(r => r.classList.remove("slr-hidden"));
                    }
                });
                container.querySelectorAll(`.slr-group-row[data-pgid="${gid}"]`).forEach(r => r.classList.remove("slr-hidden"));
            } else {
                l1.classList.add("folded");
                container.querySelectorAll(`[data-pgid="${gid}"]`).forEach(el => el.classList.add("slr-hidden"));
                container.querySelectorAll(`.slr-group-row[data-pgid="${gid}"]`).forEach(r => r.classList.add("slr-hidden"));
            }
            return;
        }

        // Fold level 2
        const l2 = t.closest(".slr-group-l2");
        if (l2) {
            const gid = l2.getAttribute("data-gid");
            const container = ev.currentTarget;
            const folded = l2.classList.contains("folded");
            if (folded) {
                l2.classList.remove("folded");
                container.querySelectorAll(`.slr-group-row[data-gid="${gid}"]`).forEach(r => r.classList.remove("slr-hidden"));
            } else {
                l2.classList.add("folded");
                container.querySelectorAll(`.slr-group-row[data-gid="${gid}"]`).forEach(r => r.classList.add("slr-hidden"));
            }
            return;
        }

        // Fold single-level
        const l1only = t.closest(".slr-group-header");
        if (l1only) {
            const gid = l1only.getAttribute("data-gid");
            const container = ev.currentTarget;
            const folded = l1only.classList.contains("folded");
            if (folded) {
                l1only.classList.remove("folded");
                container.querySelectorAll(`.slr-group-row[data-gid="${gid}"]`).forEach(r => r.classList.remove("slr-hidden"));
            } else {
                l1only.classList.add("folded");
                container.querySelectorAll(`.slr-group-row[data-gid="${gid}"]`).forEach(r => r.classList.add("slr-hidden"));
            }
            return;
        }

        // Export Excel (dari dalam konten jika ada)
        if (t.closest(".js_export_excel")) {
            this.exportExcel();
        }
    }

    // Tutup dropdown saat klik di topbar area selain dropdown
    handleClick(ev) {
        if (this.state.groupDropdownOpen) {
            this.state.groupDropdownOpen = false;
        }
    }

    exportExcel() {
        const params = new URLSearchParams();
        if (this.state.check_date) params.set("check_date", this.state.check_date);
        if (this.state.group_by) params.set("group_by", this.state.group_by);
        if (this.state.group_by2) params.set("group_by2", this.state.group_by2);
        const company_ids = this._getActiveCompanyIds();
        if (company_ids.length) params.set("company_ids", company_ids.join(","));
        window.location.href = `/stock_lot_report/export_excel?${params.toString()}`;
    }
}

StockLotReport.template = "stock_lot_report.client_template";
registry.category("actions").add("stock_lot_report.client_action", StockLotReport);
