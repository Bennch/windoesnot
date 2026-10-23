CXXFLAGS ?= -O2
CXXFLAGS += -shared -fPIC -fno-gnu-unique -std=c++23 -DNDEBUG -Wno-c++11-narrowing
INCLUDES = $(shell pkg-config --cflags pixman-1 libdrm hyprland libinput libudev wayland-server xkbcommon)

SRC = main.cpp
TARGET = hyprdrag.so

all: $(TARGET)

$(TARGET): $(SRC) globals.hpp
	$(CXX) $(CXXFLAGS) $(INCLUDES) $(SRC) -o $@ $(LDFLAGS)

clean:
	$(RM) ./$(TARGET)

.PHONY: all clean
