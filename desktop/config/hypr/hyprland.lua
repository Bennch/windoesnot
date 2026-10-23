-- WinDoesNot desktop entry point
local directory = debug.getinfo(1, "S").source:sub(2):match("(.*/)")
dofile(directory .. "lua/init.lua")
