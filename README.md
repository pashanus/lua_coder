Одной из задач данного хакатона было сделать агента/мультигентую систему, которая будет генерировать lua код, при этом система должна быть локальной и легковесной. Чтобы это реализовать мне понадобились qwen2.5-coder:7b в качестве кодера и  llama3.1:8b в качестве некого планёра, который объясняет кодеру как именно нужно реализовать задание, которое поступило на вход от пользователя.

Общая система имела следующий вид:

1. user prompt

     1.1 correction (situationally)
3. generate prompt        
4. code                   
5. tests for code            
6. busted, luacheck          
7. planner check                

     6.1 instruction for fix(if need)  

     6.2 fix(if need)             

     6.3 busted, luacheck(if need)              
8. planner → finish/fix      
9. output code and json
