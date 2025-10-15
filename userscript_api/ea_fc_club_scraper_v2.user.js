// ==UserScript==
// @name         EA FC 26 Club Scraper v2
// @namespace    http://tampermonkey.net/
// @version      2.0
// @description  Extract owned players from EA FC Web App and send to local API (using EA services API)
// @author       FUT Builder
// @match        https://www.ea.com/fifa/ultimate-team/web-app/*
// @match        https://www.ea.com/*/fifa/ultimate-team/web-app/*
// @match        https://www.easports.com/*/ea-sports-fc/ultimate-team/web-app/*
// @match        https://www.ea.com/ea-sports-fc/ultimate-team/web-app/*
// @grant        GM_xmlhttpRequest
// @connect      localhost
// @connect      127.0.0.1
// ==/UserScript==

(function() {
    'use strict';

    const API_URL = 'http://localhost:5000/api/my-club';
    const DEFAULT_SEARCH_BATCH_SIZE = 91;
    let isScraperActive = false;

    // Create UI button
    function createScraperButton() {
        // Wait for EA services to be available
        const checkServices = setInterval(() => {
            if (typeof services !== 'undefined' && services.Club) {
                clearInterval(checkServices);

                const button = document.createElement('button');
                button.id = 'fut-scraper-btn';
                button.textContent = 'Export Club to Squad Builder';
                button.style.cssText = `
                    position: fixed;
                    top: 10px;
                    right: 10px;
                    z-index: 10000;
                    padding: 12px 24px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    cursor: pointer;
                    font-weight: bold;
                    font-size: 14px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    transition: all 0.3s ease;
                `;

                button.addEventListener('mouseover', () => {
                    button.style.transform = 'translateY(-2px)';
                    button.style.boxShadow = '0 6px 12px rgba(0,0,0,0.15)';
                });

                button.addEventListener('mouseout', () => {
                    button.style.transform = 'translateY(0)';
                    button.style.boxShadow = '0 4px 6px rgba(0,0,0,0.1)';
                });

                button.addEventListener('click', startScraping);
                document.body.appendChild(button);

                console.log('[Squad Builder] Button created, EA services available');
            }
        }, 1000);
    }

    // Show notification
    function showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.innerHTML = `
            <div style="font-weight: bold; margin-bottom: 5px;">
                ${type === 'success' ? '✓' : type === 'error' ? '✗' : 'ℹ'} Squad Builder
            </div>
            <div>${message}</div>
        `;
        notification.style.cssText = `
            position: fixed;
            top: 70px;
            right: 10px;
            z-index: 10001;
            padding: 15px 20px;
            background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3b82f6'};
            color: white;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            max-width: 320px;
            font-size: 13px;
            animation: slideIn 0.3s ease;
        `;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, type === 'error' ? 5000 : 3000);
    }

    // Fetch all players from club using EA services
    async function fetchPlayers() {
        return new Promise((resolve) => {
            services.Club.clubDao.resetStatsCache();
            services.Club.getStats();

            let offset = 0;
            const batchSize = DEFAULT_SEARCH_BATCH_SIZE;
            let result = [];

            const fetchBatch = () => {
                const searchCriteria = new UTBucketedItemSearchViewModel().searchCriteria;
                searchCriteria.count = batchSize;
                searchCriteria.offset = offset;
                // Don't set type - let it default to all items

                services.Club.search(searchCriteria).observe(
                    this,
                    function(sender, response) {
                        if (response.success) {
                            const items = response.response.items || [];
                            result = result.concat(items);

                            console.log(`[Squad Builder] Batch: ${items.length} items, total: ${result.length}`);

                            // Check if there are more items
                            if (
                                Math.floor(response.status / 100) === 2 &&
                                !response.response.retrievedAll
                            ) {
                                offset += batchSize;
                                fetchBatch();
                                return;
                            }
                        }
                        resolve(result);
                    }
                );
            };

            fetchBatch();
        });
    }

    // Start scraping process
    async function startScraping() {
        if (isScraperActive) {
            showNotification('Scraping already in progress...', 'info');
            return;
        }

        if (typeof services === 'undefined' || !services.Club) {
            showNotification('EA services not available. Please wait for app to load.', 'error');
            return;
        }

        isScraperActive = true;

        try {
            showNotification('Fetching your club players...', 'info');
            console.log('[Squad Builder] Starting club scrape...');

            const players = await fetchPlayers();

            if (!players || players.length === 0) {
                showNotification('No players found in your club.', 'error');
                isScraperActive = false;
                return;
            }

            console.log(`[Squad Builder] Found ${players.length} players`);

            // Extract definitionIds (EA player IDs)
            const playerIds = players
                .filter(p => p && p.definitionId)
                .map(p => p.definitionId);

            console.log(`[Squad Builder] Sending ${playerIds.length} player IDs to API...`);
            showNotification(`Sending ${playerIds.length} players to Squad Builder...`, 'info');

            // Send to local API
            GM_xmlhttpRequest({
                method: 'POST',
                url: API_URL,
                headers: {
                    'Content-Type': 'application/json'
                },
                data: JSON.stringify({
                    player_ea_ids: playerIds
                }),
                onload: function(response) {
                    try {
                        const result = JSON.parse(response.responseText);
                        if (result.success) {
                            showNotification(
                                `Successfully exported ${result.count} players to Squad Builder!`,
                                'success'
                            );
                            console.log('[Squad Builder] Export successful:', result);
                        } else {
                            showNotification(
                                `Error: ${result.error}`,
                                'error'
                            );
                            console.error('[Squad Builder] API error:', result);
                        }
                    } catch (e) {
                        showNotification('Error parsing API response', 'error');
                        console.error('[Squad Builder] Parse error:', e);
                    }
                    isScraperActive = false;
                },
                onerror: function(error) {
                    showNotification(
                        'Failed to connect to API. Make sure Flask server is running on localhost:5000',
                        'error'
                    );
                    console.error('[Squad Builder] Connection error:', error);
                    isScraperActive = false;
                }
            });

        } catch (error) {
            showNotification('Error fetching players: ' + error.message, 'error');
            console.error('[Squad Builder] Scraping error:', error);
            isScraperActive = false;
        }
    }

    // Initialize
    function init() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', createScraperButton);
        } else {
            createScraperButton();
        }
    }

    init();

    // Add CSS animations
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideIn {
            from {
                transform: translateX(400px);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        @keyframes slideOut {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(400px);
                opacity: 0;
            }
        }
    `;
    document.head.appendChild(style);

    console.log('[Squad Builder] Userscript loaded successfully!');
})();
