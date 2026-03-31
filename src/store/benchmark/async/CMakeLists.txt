add_subdirectory(common)
add_subdirectory(retwis)

# set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -DNDEBUG -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -static-libasan -static-libubsan")

file(GLOB SourceFiles "${CMAKE_CURRENT_SOURCE_DIR}/*.cc")

add_executable(benchmark ${SourceFiles})
target_include_directories(benchmark PUBLIC ${CMAKE_SOURCE_DIR} ${CMAKE_BINARY_DIR})
target_link_libraries(benchmark BenchmarkCommon BenchmarkRetwis StoreStrong Common)