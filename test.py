import math
import turtle

def drawCircle(t, x, y, radius):
    # Lift the pen to move to the starting position without drawing
    t.up()
    # Adjust starting position
    start_angle = 90
    t.goto(x, y - radius)
    t.setheading(start_angle)
    t.down()

    # Calculate the distance to move for each step of the circle
    distance = (2.0 * math.pi * radius) / 120.0

    # Draw the circle with 120 segments
    for _ in range(120):
        t.forward(distance)
        t.left(3)

def main():
    # Create a turtle object
    t = turtle.Turtle()
    t.speed(0)  # Fastest drawing speed

    # Set initial coordinates and radius for the circle
    x = 50
    y = 75
    radius = 100

    # Call the function to draw the circle
    drawCircle(t, x, y, radius)

    # Finish
    turtle.done()

if __name__ == "__main__":
    main()
