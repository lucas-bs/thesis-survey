document.addEventListener('DOMContentLoaded', () => {
    const grid = document.getElementById('grid');
    const scoreElement = document.getElementById('score');
    const cardCountElement = document.getElementById('card-count');
    const revealBtn = document.getElementById('reveal-btn');
    let selectedCards = new Set();
    let gamePhase = 'selection';
    let isSelecting = false;
    let gamePlayed = false;
    const nextButton = document.getElementById('next-button');
    if (nextButton) {
        nextButton.disabled = true; // Disable the Next button when the page loads
    }


    // Create grid
    for (let i = 0; i < 64; i++) {
        const card = document.createElement('div');
        card.classList.add('boxes');
        card.dataset.index = i;
        card.addEventListener('mousedown', (e) => startSelecting(e, card));
        card.addEventListener('mouseover', () => selectCard(card));
        card.addEventListener('touchstart', (e) => startSelecting(e, card));
        card.addEventListener('touchmove', (e) => handleTouchMove(e));
        grid.appendChild(card);
    }

    document.addEventListener('mouseup', stopSelecting);
    document.addEventListener('touchend', stopSelecting);

    function startSelecting(e, card) {
        e.preventDefault(); // Prevent default touch behavior
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

    function handleTouchMove(e) {
        if (!isSelecting) return;
        e.preventDefault(); // Prevent scrolling while selecting
        const touch = e.touches[0];
        const card = document.elementFromPoint(touch.clientX, touch.clientY);
        if (card && card.classList.contains('boxes')) {
            selectCard(card);
        }
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

        // Only show confidence modal if not in trial
        if (!isTrial) {
            const confidenceModal = new bootstrap.Modal(document.getElementById('confidenceModal'), {
                backdrop: 'static', // Prevent closing on backdrop click
                keyboard: false // Prevent closing with the ESC key
            });
            console.log('Modal shown');
            confidenceModal.show();

            // Enable the submit button when a confidence level is selected
            const confidenceOptions = document.querySelectorAll('input[name="confidence"]');
            confidenceOptions.forEach(option => {
                option.addEventListener('change', () => {
                    document.getElementById('submitConfidence').disabled = false;
                });
            });

            // Handle the submit button click
            document.getElementById('submitConfidence').addEventListener('click', async () => {
                const selectedConfidence = document.querySelector('input[name="confidence"]:checked');

                if (!selectedConfidence) {
                    alert('Please select a confidence level');
                    return;
                }

                const confidenceValue = selectedConfidence.value;
                confidenceModal.hide();

                await proceedWithReveal(confidenceValue);
            });
        } else {
            await proceedWithReveal();
        }
    });

    async function proceedWithReveal(confidenceValue = null) {
        gamePhase = 'reveal';
        revealBtn.disabled = true;

        const revealData = {
            selected_cards: Array.from(selectedCards),
            task_number: currentTaskNumber,
            is_trial: isTrial,
            confidence: confidenceValue  // Always include confidence, even if null
        };

        const response = await fetch('/api/reveal', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(revealData),
        });

        const result = (await response.json());

        if (response.status === 409) {
            window.location.href = `/bret_game/${result.next_task}`;
            return;
        }

        // Existing reveal logic remains the same
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
        revealBtn.textContent = 'Game Over';
        revealBtn.disabled = true;
        gamePhase = 'end';
        gamePlayed = true;
        enableNextButton();
    }

    function enableNextButton() {
        const nextButton = document.getElementById('next-button');
        if (nextButton) {
            nextButton.disabled = false;
        }
    }

/*
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
    */
});
