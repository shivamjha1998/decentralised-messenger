const express = require('express');
const http = require('http');
const app = express();
const server = http.createServer(app);
const io = require('socket.io')(server, {
    cors: {
        origin: "*",
        methods: ["GET", "POST"]
    }
});

// Serve the static HTML file we will create next
app.use(express.static(__dirname));

io.on("connection", (socket) => {
    // 1. Give the user their own ID
    socket.emit("me", socket.id);

    // 2. Event: User disconnects
    socket.on("disconnect", () => {
        socket.broadcast.emit("callEnded");
    });

    // 3. Event: Sending a Call (Signaling)
    // "data" contains the WebRTC offer (the map)
    socket.on("callUser", (data) => {
        io.to(data.userToCall).emit("callUser", {
            signal: data.signalData,
            from: data.from
        });
    });

    // 4. Event: Answering a Call
    // "data" contains the WebRTC answer
    socket.on("answerCall", (data) => {
        io.to(data.to).emit("callAccepted", data.signal);
    });
});

server.listen(5000, () => console.log('Server is running on port 5000'));