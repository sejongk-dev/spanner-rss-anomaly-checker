add_subdirectory(common)
add_subdirectory(strongstore)
add_subdirectory(benchmark/async)

# set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -DNDEBUG -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -static-libasan -static-libubsan")

file(GLOB SourceFiles "${CMAKE_CURRENT_SOURCE_DIR}/*.cc")

add_executable(server ${SourceFiles})
target_include_directories(server PUBLIC ${CMAKE_SOURCE_DIR} ${CMAKE_BINARY_DIR})
target_link_libraries(server StoreStrong StoreCommon StoreCommonBackend StoreCommonFrontend Common)