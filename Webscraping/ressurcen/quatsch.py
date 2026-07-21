from ursina import *
import math

app = Ursina(borderless=False, title='Alpine Skiing Prototype')

# ==========================================
# 1. ENVIRONMENT & GRAPHICS
# ==========================================
# Add a sky
Sky(color=color.rgb(135, 206, 235))

# Lighting for depth and shadows
sun = DirectionalLight(shadow_map_resolution=(2048,2048))
sun.look_at(Vec3(1,-1,-1))

# ==========================================
# 2. CUSTOM TERRAIN GENERATION (The "Set" Mountain)
# ==========================================
# We generate a grid of vertices to create a realistic U-shaped valley
terrain_width = 60
terrain_depth = 300
segments_x = 60
segments_z = 300

vertices = []
triangles = []
uvs = []

# Build the vertex grid
for z in range(segments_z + 1):
    for x in range(segments_x + 1):
        # Normalize coordinates to -1, 1 range
        nx = x / segments_x * 2 - 1
        nz = z / segments_z
        
        # Create a U-shaped valley curve for the X axis
        valley_curve = (nx ** 2) * 30 
        
        # Create a steep downward slope for the Z axis
        downward_slope = nz * 120 
        
        # Add some natural bumpy noise
        noise = math.sin(x * 0.5) * math.cos(z * 0.2) * 1.5
        
        y = valley_curve + downward_slope + noise
        
        vertices.append(Vec3(x - segments_x/2, -y, z - segments_z/2))
        uvs.append(Vec2(x / segments_x, z / segments_z))

# Connect vertices into triangles to form the ground mesh
for z in range(segments_z):
    for x in range(segments_x):
        curr = z * (segments_x + 1) + x
        next_curr = curr + 1
        below = curr + (segments_x + 1)
        next_below = below + 1
        
        triangles.append(curr)
        triangles.append(below)
        triangles.append(next_curr)
        
        triangles.append(next_curr)
        triangles.append(below)
        triangles.append(next_below)

# Create the terrain mesh and apply a snowy texture/color
mountain_mesh = Mesh(vertices=vertices, triangles=triangles, uvs=uvs)
terrain = Entity(
    model=mountain_mesh, 
    color=color.rgb(240, 245, 255), # Slight blue tint for snow
    texture='white_cube',            # Built-in Ursina texture for snow detail
    collider='mesh',                 # Perfect collision for bumpy terrain
)

# ==========================================
# 3. THE SKIER
# ==========================================
skier = Entity(
    model='cube', 
    color=color.rgb(20, 20, 80), # Dark blue ski suit
    scale=(0.8, 1.8, 0.8),
    position=(0, 0, -140),       # Start near the top of the generated valley
    collider='box'
)

# ==========================================
# 4. GAME VARIABLES & UI
# ==========================================
speed = 0
max_speed = 60
acceleration = 12
turn_speed = 4

# Speed HUD
speed_text = Text(text='Speed: 0 km/h', position=(-0.85, 0.45), scale=2, color=color.black)
instruction_text = Text(text='A/D to Steer', position=(-0.15, -0.45), scale=1.5, color=color.dark_gray)

# Camera offset settings
cam_y_offset = 5
cam_z_offset = -12

# ==========================================
# 5. CORE GAME LOOP & ADVANCED PHYSICS
# ==========================================
def update():
    global speed
    
    if held_keys['escape']:
        application.quit()

    # --- 1. TERRAIN DETECTION ---
    # Shoot a raycast straight down to find the exact ground and its angle
    ray = raycast(skier.position, Vec3(0,-1,0), distance=5, ignore=[skier])
    
    if not ray.hit:
        return # Don't do physics if we are somehow airborne off the map

    ground_normal = ray.world_normal
    skier.position = ray.world_point + Vec3(0, 0.9, 0) # Stick to ground

    # --- 2. REALISTIC SLOPE PHYSICS ---
    # Gravity vector pointing straight down
    gravity = Vec3(0, -1, 0)
    
    # Calculate how much of that gravity is pushing us ALONG the slope
    # Formula: Projection = Gravity - (Gravity dot Normal) * Normal
    dot_product = gravity.x*ground_normal.x + gravity.y*ground_normal.y + gravity.z*ground_normal.z
    slide_direction = Vec3(
        gravity.x - dot_product * ground_normal.x,
        gravity.y - dot_product * ground_normal.y,
        gravity.z - dot_product * ground_normal.z
    ).normalized()

    # Accelerate based on the steepness of the slope
    # (steeper slope = stronger slide direction = faster acceleration)
    steepness_factor = abs(slide_direction.y) 
    speed += acceleration * steepness_factor * time.dt
    speed = min(speed, max_speed) # Cap speed

    # --- 3. MOVEMENT & STEERING ---
    # Move forward along the slope's natural slide direction
    skier.position += slide_direction * speed * time.dt

    # Calculate left/right vectors relative to the slope so turning feels natural
    forward = Vec3(-slide_direction.x, 0, -slide_direction.z).normalized()
    right = Vec3(forward.z, 0, -forward.x)

    # Apply steering
    turn_input = held_keys['d'] - held_keys['a']
    skier.position += right * turn_input * turn_speed * time.dt

    # Rotate skier to face down the slope
    skier.rotation_y = math.degrees(math.atan2(slide_direction.x, slide_direction.z))
    # Tilt skier based on steering
    skier.rotation_z = -turn_input * 15 

    # --- 4. SMOOTH CINEMATIC CAMERA ---
    # Calculate desired camera position behind the skier
    desired_cam_pos = skier.position + Vec3(0, cam_y_offset, cam_z_offset)
    # Smoothly move camera to desired position (Lerp)
    camera.position = lerp(camera.position, desired_cam_pos, time.dt * 5)
    # Make camera look slightly ahead of the skier
    look_target = skier.position + slide_direction * 10
    camera.look_at(look_target)

    # --- 5. UPDATE UI ---
    speed_text.text = f'Speed: {int(speed * 3.6)} km/h' # Convert m/s to km/h roughly

# ==========================================
# 6. WHERE TO ADD OBSTACLES (For You!)
# ==========================================
# To add a tree, simply copy and paste this code down here!
# The Y position doesn't matter much because we can use raycasts to stick 
# them to the ground perfectly in a real setup, but here is an example:

def create_tree(x, z):
    # Find the exact height of the ground at this X and Z coordinate
    ray = raycast(Vec3(x, 100, z), Vec3(0,-1,0), distance=200, ignore=[skier])
    if ray.hit:
        y = ray.world_point.y
        # Trunk
        Entity(model='cube', color=color.brown, scale=(0.5, 4, 0.5), position=(x, y+2, z), collider='box')
        # Leaves
        Entity(model='cube', color=color.green, scale=(3, 4, 3), position=(x, y+6, z), collider='box')

# Example trees placed in the valley
create_tree(-8, -100)
create_tree(10, -80)
create_tree(-15, -50)
create_tree(5, -20)

app.run()