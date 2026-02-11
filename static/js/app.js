// Initialize Lucide Icons
lucide.createIcons();

// Custom Micro-animations & Interactions
document.addEventListener('DOMContentLoaded', () => {
    const bars = document.querySelectorAll('.bar');
    
    // Add staggered animation to bars
    bars.forEach((bar, index) => {
        setTimeout(() => {
            bar.style.opacity = '1';
        }, index * 100);
    });

    // Handle Nav Item Clicks
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            navItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');
        });
    });

    // Mock Live Lead Update
    setInterval(() => {
        const leadList = document.querySelector('.lead-list');
        const firstLead = leadList.querySelector('.lead-item');
        
        // Simulating a new lead drop-in
        if (Math.random() > 0.7) {
            const names = ['@leo_vlogs', '@fitness_hero', '@yoga_jane', '@travel_tok'];
            const randomName = names[Math.floor(Math.random() * names.length)];
            
            const newLead = document.createElement('div');
            newLead.className = 'lead-item';
            newLead.style.opacity = '0';
            newLead.style.transform = 'translateX(-20px)';
            newLead.innerHTML = `
                <div class="lead-avatar">${randomName.substring(1, 3).toUpperCase()}</div>
                <div class="lead-details">
                    <p class="lead-name">${randomName}</p>
                    <p class="lead-status">Just commented #RECIPE</p>
                </div>
                <p class="lead-time">Just now</p>
            `;
            
            leadList.prepend(newLead);
            
            // Remove last item to keep list clean
            if (leadList.children.length > 5) {
                leadList.removeChild(leadList.lastElementChild);
            }

            // Animate in
            setTimeout(() => {
                newLead.style.transition = 'all 0.5s cubic-bezier(0.4, 0, 0.2, 1)';
                newLead.style.opacity = '1';
                newLead.style.transform = 'translateX(0)';
            }, 50);
        }
    }, 5000);
});
