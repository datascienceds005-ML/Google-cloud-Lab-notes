function initSocket(io) {
  io.on('connection', (socket) => {
    console.log('🔌 User connected:', socket.id);

    // Join HR dashboard room
    socket.on('join-hr-dashboard', () => {
      socket.join('hr-dashboard');
      console.log('👤 User joined HR dashboard room');
    });

    // Join intern room for personal updates
    socket.on('join-intern-room', (internId) => {
      socket.join(`intern-${internId}`);
      console.log(`👤 User joined intern room: intern-${internId}`);
    });

    socket.on('disconnect', () => {
      console.log('🔌 User disconnected:', socket.id);
    });
  });
}

module.exports = { initSocket };
