document.addEventListener('DOMContentLoaded', () => {
    const grid = document.getElementById('grid');
    const scoreElement = document.getElementById('score');
    const cardCountElement = document.getElementById('card-count');
    const revealBtn = document.getElementById('reveal-btn');
    let selectedCards = new Set();
    let gamePhase = 'selection';

    // Create grid
    for (let i = 0; i < 64; i++) {
        const card = document.createElement('div');
        card.classList.add('boxes');
        card.dataset.index = i;
        card.addEventListener('mousedown', () => startSelecting(card));
        card.addEventListener('mouseover', () => selectCard(card));
        grid.appendChild(card);
    }

    document.addEventListener('mouseup', () => stopSelecting());

    function startSelecting(card) {
        if (gamePhase !== 'selection') return;
        isSelecting = true;
        toggleCard(card);
    }

    function selectCard(card) {
        if (!isSelecting) return;
        toggleCard(card);
    }

    function stopSelecting() {
        isSelecting = false;
    }

    function toggleCard(card) {
        const index = parseInt(card.dataset.index);

        if (selectedCards.has(index)) {
            selectedCards.delete(index);
            card.classList.remove('selected');
        } else {
            selectedCards.add(index);
            card.classList.add('selected');
        }

        updateScore();
        updateCardCount();
    }

    function updateScore() {
        const potentialPayout = (selectedCards.size * 0.2).toFixed(2);
        scoreElement.textContent = `Your potential payout is: €${potentialPayout}`;
    }

    function updateCardCount() {
        cardCountElement.textContent = `Selected: ${selectedCards.size} | Remaining: ${64 - selectedCards.size}`;
    }

    revealBtn.addEventListener('click', async () => {
        if (gamePhase !== 'selection') return;

        gamePhase = 'reveal';
        revealBtn.disabled = true;

        const response = await fetch('/api/reveal', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ selected_cards: Array.from(selectedCards) }),
        });

        const result = (await response.json());

        // Reveal cards
        grid.childNodes.forEach((card, index) => {
            if (selectedCards.has(index)) {
                if (index === result.bomb_index) {
                    card.classList.add('bomb');
                    card.textContent = 'X';
                    result.score = 0;
                } else {
                    card.classList.add('safe');
                    card.textContent = '€';
                }
            }
            card.classList.remove('selected');
            card.classList.add('revealed');
        });

        scoreElement.textContent = `Final payout: €${result.score.toFixed(2)}`;
        revealBtn.textContent = 'Play Again';
        revealBtn.disabled = false;
        gamePhase = 'end';
    });

    revealBtn.addEventListener('click', () => {
        if (gamePhase === 'end') {
            // Reset the game
            selectedCards.clear();
            gamePhase = 'selection';
            revealBtn.textContent = 'Turn Cards';
            grid.childNodes.forEach(card => {
                card.classList.remove('selected', 'revealed', 'bomb', 'safe');
                card.textContent = '';
            });
            updateScore();
            updateCardCount();
        }
    });
});