(function () {
    const STORAGE_KEY = 'placementSidebarCollapsed';

    function initSidebarToggle() {
        const sidebar = document.getElementById('appSidebar');
        const toggle = document.getElementById('sidebarToggle');
        const layout = document.querySelector('.app-layout');

        if (!sidebar || !toggle) {
            return;
        }

        function setCollapsed(collapsed) {
            sidebar.classList.toggle('collapsed', collapsed);
            if (layout) {
                layout.classList.toggle('sidebar-collapsed', collapsed);
            }
            try {
                localStorage.setItem(STORAGE_KEY, collapsed ? '1' : '0');
            } catch (e) {
                /* ignore */
            }
        }

        if (localStorage.getItem(STORAGE_KEY) === '1') {
            setCollapsed(true);
        }

        toggle.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            setCollapsed(!sidebar.classList.contains('collapsed'));
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initSidebarToggle);
    } else {
        initSidebarToggle();
    }
})();
